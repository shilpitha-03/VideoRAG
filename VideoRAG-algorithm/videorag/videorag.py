import os
import sys
import json
import shutil
import asyncio
import multiprocessing
from dataclasses import asdict, dataclass, field
from datetime import datetime
from functools import partial
from typing import Callable, Dict, List, Optional, Type, Union, cast
from transformers import AutoModel, AutoTokenizer
import tiktoken


from ._llm import (
    LLMConfig,
    openai_config,
    azure_openai_config,
    ollama_config
)
from ._op import (
    chunking_by_video_segments,
    extract_entities,
    get_chunks,
    videorag_query,
    videorag_query_multiple_choice,
)
from ._storage import (
    JsonKVStorage,
    NanoVectorDBStorage,
    NanoVectorDBVideoSegmentStorage,
    NetworkXStorage,
)
from ._utils import (
    EmbeddingFunc,
    compute_mdhash_id,
    limit_async_func_call,
    wrap_embedding_func_with_attrs,
    convert_response_to_json,
    always_get_an_event_loop,
    logger,
)
from .base import (
    BaseGraphStorage,
    BaseKVStorage,
    BaseVectorStorage,
    StorageNameSpace,
    QueryParam,
)
from ._videoutil import(
    split_video,
    speech_to_text,
    segment_caption,
    merge_segment_information,
    saving_video_segments,
)

def caption_in_main_process(
    video_name, video_path, segment_index2name, 
    transcripts, segment_times_info, caption_model, caption_tokenizer
):
    """Run captioning in the main process on GPU.
    
    Replaces the multiprocessing subprocess approach which cannot
    initialize CUDA in forked processes on Linux.
    Returns a regular dict of captions keyed by segment index.
    """
    import numpy as np
    from PIL import Image
    from tqdm import tqdm
    from moviepy.video.io.VideoFileClip import VideoFileClip
    import torch

    def encode_video(video, frame_times):
        frames = []
        for t in frame_times:
            frames.append(video.get_frame(t))
        frames = np.stack(frames, axis=0)
        frames = [Image.fromarray(v.astype('uint8')).resize((1280, 720)) 
                  for v in frames]
        return frames

    captions = {}
    with VideoFileClip(video_path) as video:
        for index in tqdm(
            segment_index2name, 
            desc=f"Captioning Video {video_name}"
        ):
            frame_times = segment_times_info[index]["frame_times"]
            video_frames = encode_video(video, frame_times)
            segment_transcript = transcripts[index]
            query = (
                f"The transcript of the current video:\n"
                f"{segment_transcript}.\n"
                f"Now provide a description (caption) of the video in English."
            )
            msgs = [{'role': 'user', 'content': video_frames + [query]}]
            params = {"use_image_id": False, "max_slice_nums": 2}
            result = caption_model.chat(
                image=None,
                msgs=msgs,
                tokenizer=caption_tokenizer,
                **params
            )
            captions[index] = result.replace("\n", "").replace(
                "<|endoftext|>", ""
            )
    return captions
@dataclass
class VideoRAG:
    working_dir: str = field(
        default_factory=lambda: f"./videorag_cache_{datetime.now().strftime('%Y-%m-%d-%H:%M:%S')}"
    )
    
    # video
    threads_for_split: int = 10
    video_segment_length: int = 30 # seconds
    rough_num_frames_per_segment: int = 5 # frames
    fine_num_frames_per_segment: int = 15 # frames
    video_output_format: str = "mp4"
    audio_output_format: str = "mp3"
    video_embedding_batch_num: int = 2
    segment_retrieval_top_k: int = 4
    video_embedding_dim: int = 1024
    
    # query
    retrieval_topk_chunks: int = 2
    query_better_than_threshold: float = 0.2
    
    # graph mode
    enable_local: bool = True
    enable_naive_rag: bool = True

    # text chunking
    chunk_func: Callable[
        [
            list[list[int]],
            List[str],
            tiktoken.Encoding,
            Optional[int],
        ],
        List[Dict[str, Union[str, int]]],
    ] = chunking_by_video_segments
    chunk_token_size: int = 1200
    # chunk_overlap_token_size: int = 100
    tiktoken_model_name: str = "gpt-4o"

    # entity extraction
    entity_extract_max_gleaning: int = 1
    entity_summary_to_max_tokens: int = 500

    # Change to your LLM provider
    llm: LLMConfig = field(default_factory=openai_config)
    
    # entity extraction
    entity_extraction_func: callable = extract_entities
    
    # storage
    key_string_value_json_storage_cls: Type[BaseKVStorage] = JsonKVStorage
    vector_db_storage_cls: Type[BaseVectorStorage] = NanoVectorDBStorage
    vs_vector_db_storage_cls: Type[BaseVectorStorage] = NanoVectorDBVideoSegmentStorage
    vector_db_storage_cls_kwargs: dict = field(default_factory=dict)
    graph_storage_cls: Type[BaseGraphStorage] = NetworkXStorage
    enable_llm_cache: bool = True

    # extension
    always_create_working_dir: bool = True
    addon_params: dict = field(default_factory=dict)
    convert_response_to_json_func: callable = convert_response_to_json

    def load_caption_model(self, debug=False):
        if not debug:
            minicpm_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), 
                '..', 'MiniCPM-V-2_6-int4'
            )
            minicpm_path = os.path.normpath(minicpm_path)
            self.caption_model = AutoModel.from_pretrained(
                minicpm_path, trust_remote_code=True
            ).cuda()
            self.caption_tokenizer = AutoTokenizer.from_pretrained(
                minicpm_path, trust_remote_code=True
            )
            self.caption_model.eval()
        else:
            self.caption_model = None
            self.caption_tokenizer = None
    
    def __post_init__(self):
        _print_config = ",\n  ".join([f"{k} = {v}" for k, v in asdict(self).items()])
        logger.debug(f"VideoRAG init with param:\n\n  {_print_config}\n")
        
        if not os.path.exists(self.working_dir) and self.always_create_working_dir:
            logger.info(f"Creating working directory {self.working_dir}")
            os.makedirs(self.working_dir)

        self.video_path_db = self.key_string_value_json_storage_cls(
            namespace="video_path", global_config=asdict(self)
        )
        
        self.video_segments = self.key_string_value_json_storage_cls(
            namespace="video_segments", global_config=asdict(self)
        )

        self.text_chunks = self.key_string_value_json_storage_cls(
            namespace="text_chunks", global_config=asdict(self)
        )

        self.llm_response_cache = (
            self.key_string_value_json_storage_cls(
                namespace="llm_response_cache", global_config=asdict(self)
            )
            if self.enable_llm_cache
            else None
        )

        self.chunk_entity_relation_graph = self.graph_storage_cls(
            namespace="chunk_entity_relation", global_config=asdict(self)
        )

        self.embedding_func = limit_async_func_call(self.llm.embedding_func_max_async)(wrap_embedding_func_with_attrs(
                embedding_dim = self.llm.embedding_dim,
                max_token_size = self.llm.embedding_max_token_size,
                model_name = self.llm.embedding_model_name)(self.llm.embedding_func))
        self.entities_vdb = (
            self.vector_db_storage_cls(
                namespace="entities",
                global_config=asdict(self),
                embedding_func=self.embedding_func,
                meta_fields={"entity_name"},
            )
            if self.enable_local
            else None
        )
        self.chunks_vdb = (
            self.vector_db_storage_cls(
                namespace="chunks",
                global_config=asdict(self),
                embedding_func=self.embedding_func,
            )
            if self.enable_naive_rag
            else None
        )
        
        self.video_segment_feature_vdb = (
            self.vs_vector_db_storage_cls(
                namespace="video_segment_feature",
                global_config=asdict(self),
                embedding_func=None, # we code the embedding process inside the insert() function.
            )
        )
        
        self.llm.best_model_func = limit_async_func_call(self.llm.best_model_max_async)(
            partial(self.llm.best_model_func, hashing_kv=self.llm_response_cache)
        )
        self.llm.cheap_model_func = limit_async_func_call(self.llm.cheap_model_max_async)(
            partial(self.llm.cheap_model_func, hashing_kv=self.llm_response_cache)
        )
    def insert_video(self, video_path_list=None):
        loop = always_get_an_event_loop()
        
        # Load MiniCPM-V once in main process on GPU
        # This avoids loading inside a forked subprocess which cannot initialize CUDA
        import os
        import torch
        minicpm_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'MiniCPM-V-2_6-int4')
        minicpm_path = os.path.normpath(minicpm_path)
        logger.info("Loading MiniCPM-V caption model...")
        # caption_model = AutoModel.from_pretrained(
        #     minicpm_path, 
        #     trust_remote_code=True
        # )
        # caption_model = AutoModel.from_pretrained(
        #     minicpm_path,
        #     trust_remote_code=True
        # )
        # caption_tokenizer = AutoTokenizer.from_pretrained(
        #     minicpm_path, 
        #     trust_remote_code=True
        # )
        # caption_model.eval()
        caption_model = AutoModel.from_pretrained(
            minicpm_path,
            trust_remote_code=True
        ).cuda()
        caption_tokenizer = AutoTokenizer.from_pretrained(
            minicpm_path,
            trust_remote_code=True
        )
        caption_model.eval()
        logger.info("✓ MiniCPM-V loaded on GPU")

        for video_path in video_path_list:
            # Step 0: check existence
            video_name = os.path.basename(video_path).split('.')[0]
            if video_name in self.video_segments._data:
                logger.info(f"Find the video named {os.path.basename(video_path)} in storage and skip it.")
                continue
            loop.run_until_complete(self.video_path_db.upsert(
                {video_name: video_path}
            ))

            # Step 1: split
            segment_index2name, segment_times_info = split_video(
                video_path,
                self.working_dir,
                self.video_segment_length,
                self.rough_num_frames_per_segment,
                self.audio_output_format,
            )

            # Step 2: ASR
            # transcripts = speech_to_text(
            #     video_name,
            #     self.working_dir,
            #     segment_index2name,
            #     self.audio_output_format
            # )

            transcripts = speech_to_text(
                video_name,
                self.working_dir,
                segment_index2name,
                self.audio_output_format,
                segment_times_info=segment_times_info
            )

            # Save transcripts for inspection
            import json
            transcript_save_path = os.path.join(
                self.working_dir, f'{video_name}_transcripts.json'
            )
            with open(transcript_save_path, 'w') as f:
                json.dump(transcripts, f, indent=2)
            logger.info(f"Transcripts saved to {transcript_save_path}")

            # Step 3a: Save video segments in subprocess (CPU/disk only, no CUDA)
            manager = multiprocessing.Manager()
            error_queue = manager.Queue()

            process_saving_video_segments = multiprocessing.Process(
                target=saving_video_segments,
                args=(
                    video_name,
                    video_path,
                    self.working_dir,
                    segment_index2name,
                    segment_times_info,
                    error_queue,
                    self.video_output_format,
                )
            )
            process_saving_video_segments.start()
            process_saving_video_segments.join()

            while not error_queue.empty():
                error_message = error_queue.get()
                with open('error_log_videorag.txt', 'a', encoding='utf-8') as log_file:
                    log_file.write(f"Video Name:{video_name} Error saving:\n{error_message}\n\n")
                raise RuntimeError(error_message)

            # Step 3b: Caption in main process on GPU
            # No subprocess - CUDA already initialized, runs on GPU
            logger.info(f"Captioning {video_name} on GPU...")
            captions = caption_in_main_process(
                video_name,
                video_path,
                segment_index2name,
                transcripts,
                segment_times_info,
                caption_model,
                caption_tokenizer,
            )

            # Save captions for inspection
            caption_save_path = os.path.join(
                self.working_dir, f'{video_name}_captions.json'
            )
            with open(caption_save_path, 'w') as f:
                json.dump(captions, f, indent=2)
            logger.info(f"Captions saved to {caption_save_path}")

            # Step 4: insert segments
            segments_information = merge_segment_information(
                segment_index2name,
                segment_times_info,
                transcripts,
                captions,
            )
            manager.shutdown()
            loop.run_until_complete(self.video_segments.upsert(
                {video_name: segments_information}
            ))

            # Step 5: ImageBind visual embeddings
            loop.run_until_complete(self.video_segment_feature_vdb.upsert(
                video_name,
                segment_index2name,
                self.video_output_format,
            ))

            # Step 6: delete cache
            video_segment_cache_path = os.path.join(
                self.working_dir, '_cache', video_name
            )
            if os.path.exists(video_segment_cache_path):
                shutil.rmtree(video_segment_cache_path)

            # Step 7: save
            loop.run_until_complete(self._save_video_segments())

        # Free caption model before bge-m3 loads
        del caption_model
        del caption_tokenizer
        import gc
        gc.collect()
        torch.cuda.empty_cache()
        logger.info("Caption model freed from GPU")

        loop.run_until_complete(self.ainsert(self.video_segments._data))
    # def insert_video(self, video_path_list=None):
    #     loop = always_get_an_event_loop()
    #     for video_path in video_path_list:
    #         # Step0: check the existence
    #         video_name = os.path.basename(video_path).split('.')[0]
    #         if video_name in self.video_segments._data:
    #             logger.info(f"Find the video named {os.path.basename(video_path)} in storage and skip it.")
    #             continue
    #         loop.run_until_complete(self.video_path_db.upsert(
    #             {video_name: video_path}
    #         ))
            
    #         # Step1: split the videos
    #         segment_index2name, segment_times_info = split_video(
    #             video_path, 
    #             self.working_dir, 
    #             self.video_segment_length,
    #             self.rough_num_frames_per_segment,
    #             self.audio_output_format,
    #         )
            
    #         # Step2: obtain transcript with whisper
    #         transcripts = speech_to_text(
    #             video_name, 
    #             self.working_dir, 
    #             segment_index2name,
    #             self.audio_output_format
    #         )
            
    #         # Save transcripts immediately for inspection
    #         import json
    #         transcript_save_path = os.path.join(
    #             self.working_dir, f'{video_name}_transcripts.json'
    #         )
    #         with open(transcript_save_path, 'w') as f:
    #             json.dump(transcripts, f, indent=2)
    #         logger.info(f"Transcripts saved to {transcript_save_path}")

    #         # Step3: saving video segments **as well as** obtain caption with vision language model
    #         manager = multiprocessing.Manager()
    #         captions = manager.dict()
    #         error_queue = manager.Queue()
            
    #         process_saving_video_segments = multiprocessing.Process(
    #             target=saving_video_segments,
    #             args=(
    #                 video_name,
    #                 video_path,
    #                 self.working_dir,
    #                 segment_index2name,
    #                 segment_times_info,
    #                 error_queue,
    #                 self.video_output_format,
    #             )
    #         )
            
    #         process_segment_caption = multiprocessing.Process(
    #             target=segment_caption,
    #             args=(
    #                 video_name,
    #                 video_path,
    #                 segment_index2name,
    #                 transcripts,
    #                 segment_times_info,
    #                 captions,
    #                 error_queue,
    #             )
    #         )
            
    #         # process_saving_video_segments.start()
    #         # process_segment_caption.start()
    #         # process_saving_video_segments.join()
    #         # process_segment_caption.join()
    #         # Run sequentially - parallel GPU access from separate processes crashes single-GPU setups
    #         # Save video segments first (CPU/disk only)
    #         process_saving_video_segments.start()
    #         process_saving_video_segments.join()

    #         # import ctranslate2
    #         # ctranslate2.StorageView.empty_cache()
    #         # import gc

    #         import gc
    #         gc.collect()
    #         import torch
    #         torch.cuda.empty_cache()

    #         # Then caption (GPU - MiniCPM-V loads fresh in this subprocess)
    #         process_segment_caption.start()
    #         process_segment_caption.join()
            
    #         # if raise error in this two, stop the processing
    #         while not error_queue.empty():
    #             error_message = error_queue.get()
    #             with open('error_log_videorag.txt', 'a', encoding='utf-8') as log_file:
    #                 log_file.write(f"Video Name:{video_name} Error processing:\n{error_message}\n\n")
    #             raise RuntimeError(error_message)
            
    #         # Save captions immediately for inspection
    #         caption_save_path = os.path.join(
    #             self.working_dir, f'{video_name}_captions.json'
    #         )
    #         with open(caption_save_path, 'w') as f:
    #             json.dump(dict(captions), f, indent=2)
    #         logger.info(f"Captions saved to {caption_save_path}")

    #         # Step4: insert video segments information
    #         segments_information = merge_segment_information(
    #             segment_index2name,
    #             segment_times_info,
    #             transcripts,
    #             captions,
    #         )
    #         manager.shutdown()
    #         loop.run_until_complete(self.video_segments.upsert(
    #             {video_name: segments_information}
    #         ))
            
    #         # Step5: encode video segment features
    #         loop.run_until_complete(self.video_segment_feature_vdb.upsert(
    #             video_name,
    #             segment_index2name,
    #             self.video_output_format,
    #         ))
            
    #         # Step6: delete the cache file
    #         video_segment_cache_path = os.path.join(self.working_dir, '_cache', video_name)
    #         if os.path.exists(video_segment_cache_path):
    #             shutil.rmtree(video_segment_cache_path)
            
    #         # Step 7: saving current video information
    #         loop.run_until_complete(self._save_video_segments())
        
    #     loop.run_until_complete(self.ainsert(self.video_segments._data))

    def query(self, query: str, param: QueryParam = QueryParam()):
        loop = always_get_an_event_loop()
        return loop.run_until_complete(self.aquery(query, param))

    async def aquery(self, query: str, param: QueryParam = QueryParam()):
        if param.mode == "videorag":
            response = await videorag_query(
                query,
                self.entities_vdb,
                self.text_chunks,
                self.chunks_vdb,
                self.video_path_db,
                self.video_segments,
                self.video_segment_feature_vdb,
                self.chunk_entity_relation_graph,
                self.caption_model, 
                self.caption_tokenizer,
                param,
                asdict(self),
            )
        # NOTE: update here
        elif param.mode == "videorag_multiple_choice":
            response = await videorag_query_multiple_choice(
                query,
                self.entities_vdb,
                self.text_chunks,
                self.chunks_vdb,
                self.video_path_db,
                self.video_segments,
                self.video_segment_feature_vdb,
                self.chunk_entity_relation_graph,
                self.caption_model, 
                self.caption_tokenizer,
                param,
                asdict(self),
            )
        else:
            raise ValueError(f"Unknown mode {param.mode}")
        await self._query_done()
        return response

    async def ainsert(self, new_video_segment):
        await self._insert_start()
        try:
            # ---------- chunking
            inserting_chunks = get_chunks(
                new_videos=new_video_segment,
                chunk_func=self.chunk_func,
                max_token_size=self.chunk_token_size,
            )
            _add_chunk_keys = await self.text_chunks.filter_keys(
                list(inserting_chunks.keys())
            )
            inserting_chunks = {
                k: v for k, v in inserting_chunks.items() if k in _add_chunk_keys
            }
            if not len(inserting_chunks):
                logger.warning(f"All chunks are already in the storage")
                return
            logger.info(f"[New Chunks] inserting {len(inserting_chunks)} chunks")
            if self.enable_naive_rag:
                logger.info("Insert chunks for naive RAG")
                await self.chunks_vdb.upsert(inserting_chunks)

            # TODO: no incremental update for communities now, so just drop all
            # await self.community_reports.drop()

            # ---------- extract/summary entity and upsert to graph
            logger.info("[Entity Extraction]...")
            maybe_new_kg, _, _ = await self.entity_extraction_func(
                inserting_chunks,
                knowledge_graph_inst=self.chunk_entity_relation_graph,
                entity_vdb=self.entities_vdb,
                global_config=asdict(self),
            )
            if maybe_new_kg is None:
                logger.warning("No new entities found")
                return
            self.chunk_entity_relation_graph = maybe_new_kg
            # ---------- commit upsertings and indexing
            await self.text_chunks.upsert(inserting_chunks)
        finally:
            await self._insert_done()

    async def _insert_start(self):
        tasks = []
        for storage_inst in [
            self.chunk_entity_relation_graph,
        ]:
            if storage_inst is None:
                continue
            tasks.append(cast(StorageNameSpace, storage_inst).index_start_callback())
        await asyncio.gather(*tasks)

    async def _save_video_segments(self):
        tasks = []
        for storage_inst in [
            self.video_segment_feature_vdb,
            self.video_segments,
            self.video_path_db,
        ]:
            if storage_inst is None:
                continue
            tasks.append(cast(StorageNameSpace, storage_inst).index_done_callback())
        await asyncio.gather(*tasks)
    
    async def _insert_done(self):
        tasks = []
        for storage_inst in [
            self.text_chunks,
            self.llm_response_cache,
            self.entities_vdb,
            self.chunks_vdb,
            self.chunk_entity_relation_graph,
            self.video_segment_feature_vdb,
            self.video_segments,
            self.video_path_db,
        ]:
            if storage_inst is None:
                continue
            tasks.append(cast(StorageNameSpace, storage_inst).index_done_callback())
        await asyncio.gather(*tasks)

    async def _query_done(self):
        tasks = []
        for storage_inst in [self.llm_response_cache]:
            if storage_inst is None:
                continue
            tasks.append(cast(StorageNameSpace, storage_inst).index_done_callback())
        await asyncio.gather(*tasks)
