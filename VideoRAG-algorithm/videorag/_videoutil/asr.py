import os
import csv
import logging
from faster_whisper import WhisperModel


def map_annotations_to_splits(csv_path, video_name, segment_times_info):
    """Map variable-length CSV annotations onto fixed 30s VideoRAG clips.
    
    CSV has clips at [0-9.6], [9.6-22.3], ... (cut by phase/step)
    VideoRAG splits at [0-30], [30-60], [60-90], ... (fixed windows)
    This finds all annotations overlapping each 30s window and merges them.
    """
    annotations = []
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            annotations.append({
                'start': float(row['start_time']),
                'end': float(row['end_time']),
                'phase': row.get('phase', '').strip(),
                'step': row.get('step', '').strip(),
            })

    transcripts = {}
    for index, info in segment_times_info.items():
        clip_start, clip_end = info['timestamp']

        # Find all annotations that overlap this 30s window
        overlapping = []
        for ann in annotations:
            if ann['start'] < clip_end and ann['end'] > clip_start:
                overlapping.append(ann)

        if overlapping:
            parts = []
            for ann in overlapping:
                line = f"[{ann['start']:.1f}s-{ann['end']:.1f}s]"
                if ann['phase']:
                    line += f" Phase: {ann['phase']}."
                if ann['step']:
                    line += f" Step: {ann['step']}."
                parts.append(line)
            transcripts[index] = " ".join(parts)
        else:
            transcripts[index] = ""

    print(f"✓ Mapped {len(annotations)} annotations onto "
          f"{len(segment_times_info)} clips for {video_name}")
    return transcripts


def speech_to_text(video_name, working_dir, segment_index2name,
                   audio_output_format, segment_times_info=None):
    # Check for annotations CSV first
    possible_paths = [
        os.path.join(working_dir, '..', 'annotations', f'{video_name}.csv'),
        os.path.join(working_dir, 'annotations', f'{video_name}.csv'),
    ]

    for csv_path in possible_paths:
        if os.path.exists(csv_path):
            print(f"Found annotations CSV: {csv_path}")
            if segment_times_info is not None:
                return map_annotations_to_splits(
                    csv_path, video_name, segment_times_info
                )
            else:
                print("WARNING: segment_times_info not passed, "
                      "cannot map annotations to 30s clips. "
                      "Falling back to Whisper.")
                break

    # No annotations — run Whisper
    model = WhisperModel(
        "./faster-distil-whisper-large-v3",
        device="cpu", compute_type="int8", cpu_threads=8
    )
    model.logger.setLevel(logging.WARNING)

    cache_path = os.path.join(working_dir, '_cache', video_name)
    transcripts = {}
    for index in segment_index2name:
        audio_file = os.path.join(
            cache_path,
            f'{segment_index2name[index]}.{audio_output_format}'
        )
        if os.path.exists(audio_file):
            segments, _ = model.transcribe(audio_file)
            transcripts[index] = ' '.join([s.text for s in segments]).strip()
        else:
            transcripts[index] = ""

    return transcripts


















# import os
# import torch
# import logging
# from tqdm import tqdm
# from faster_whisper import WhisperModel
# from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline

# def speech_to_text(video_name, working_dir, segment_index2name, audio_output_format):
#     # model = WhisperModel("./faster-distil-whisper-large-v3")
#     model = WhisperModel("./faster-distil-whisper-large-v3", device="cpu", compute_type="int8", cpu_threads=8)
#     # model = WhisperModel("./faster-distil-whisper-large-v3", device="cuda", compute_type="float16")  # float16 avoids the int8 cuDNN ops that fail
#     model.logger.setLevel(logging.WARNING)
    
#     cache_path = os.path.join(working_dir, '_cache', video_name)
    
#     transcripts = {}
#     for index in tqdm(segment_index2name, desc=f"Speech Recognition {video_name}"):
#         segment_name = segment_index2name[index]
#         audio_file = os.path.join(cache_path, f"{segment_name}.{audio_output_format}")

#         # if the audio file does not exist, skip it
#         if not os.path.exists(audio_file):
#             transcripts[index] = ""
#             continue
        
#         segments, info = model.transcribe(audio_file)
#         result = ""
#         for segment in segments:
#             result += "[%.2fs -> %.2fs] %s\n" % (segment.start, segment.end, segment.text)
#         transcripts[index] = result
    
#     return transcripts