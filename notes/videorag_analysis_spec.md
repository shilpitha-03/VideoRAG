# VideoRAG Analysis Instrumentation Specification

## Purpose

Add instrumentation to the VideoRAG pipeline to dump structured intermediate outputs to disk for every stage of indexing and retrieval. This enables systematic analysis of pipeline behavior without re-running expensive indexing.

This document specifies:
1. What to capture (the full list of intermediate outputs)
2. Where in the code to hook in (file and function references)
3. How to structure the outputs on disk (analysis-friendly format)

## Principles

- **Observe, don't change.** Instrumentation must not alter pipeline behavior. All hooks are pure side effects (write to disk) and never modify what gets returned.
- **Structured, parseable formats.** JSON for structured data, plain text for raw LLM outputs. No pickled objects or proprietary formats.
- **Corpus traceability is foundational.** Every clip ID, chunk ID, and entity must be resolvable back to the original video timestamp and content via a single lookup file.
- **Sampling for expensive captures.** Full data for some items (final graph, retrieval outputs), sampled subset for verbose items (raw LLM extraction responses, merge traces).
- **One folder per analytical artifact.** Per-query outputs go in per-query folders. Indexing outputs go in topic-organized files.

## Storage Location

All outputs go to local disk (not Drive — limited space there). Default base directory: `./videorag_analysis/`. Make this configurable via a command-line argument or environment variable.

```
videorag_analysis/
├── indexing/
│   ├── corpus_map.json
│   ├── clips.json
│   ├── chunks.json
│   ├── entities.json
│   ├── relationships.json
│   ├── graph_summary.json
│   ├── provenance_check.json
│   ├── aggregate_stats.json
│   ├── subgraph_samples/
│   │   ├── chunk_<id>/
│   │   │   ├── raw_llm_response.txt
│   │   │   ├── parsed_subgraph.json
│   │   │   └── chunk_corpus_info.json
│   │   └── ...
│   └── merge_traces/
│       ├── entity_<NAME>/
│       │   ├── merge_group.json
│       │   ├── resolution.json
│       │   └── corpus_trace.json
│       └── ...
└── queries/
    ├── eval_set.json
    ├── q001/
    │   ├── query.json
    │   ├── reformulations.json
    │   ├── path1.json
    │   ├── path2.json
    │   ├── path3.json
    │   ├── filter.json
    │   ├── recaption.json
    │   ├── generation.json
    │   └── timing.json
    └── q002/
        └── ...
```

---

# Part 1: Indexing Outputs

These are extracted from the index after indexing completes. Most can be derived from existing storage (text_chunks_db, NetworkX graph, VDBs) — they don't require re-running the pipeline. A few (sub-graph samples, merge traces) require hooks added during indexing.

## 1.1 Corpus Map (`indexing/corpus_map.json`)

The foundational lookup file. Every other output references this for corpus context.

```json
{
  "indexing_metadata": {
    "indexed_at": "ISO timestamp",
    "config_name": "deepseek_bge_config | openai_config | etc",
    "llm_models": {"best": "gpt-4o", "cheap": "gpt-4o-mini"},
    "embedding_model": "text-embedding-3-small",
    "visual_encoder": "ImageBind",
    "vlm": "MiniCPM-V-2_6-int4",
    "asr_model": "faster-distil-whisper-large-v3"
  },
  "videos": [
    {
      "video_name": "3b1b_nn_1_neurons",
      "file_path": "/abs/path/to/video.mp4",
      "duration_seconds": 1140,
      "duration_timestamp": "0:19:00",
      "num_clips": 38
    }
  ],
  "clips": [
    {
      "system_clip_id": "3b1b_nn_1_neurons_3",
      "video_name": "3b1b_nn_1_neurons",
      "video_file_path": "/abs/path/to/video.mp4",
      "clip_index": 3,
      "start_seconds": 90.0,
      "end_seconds": 120.0,
      "start_timestamp": "0:01:30",
      "end_timestamp": "0:02:00",
      "duration_seconds": 30.0,
      "sampled_frame_times": [93.0, 99.0, 105.0, 111.0, 117.0]
    }
  ]
}
```

**Where to hook:** After indexing completes, read from `video_segments` data structure and `split.py` outputs. Walk all videos and their clips. The clip ID format `{video_name}_{index}` is parsed in `videorag_query` — use the same parsing logic in reverse.

## 1.2 Clips (`indexing/clips.json`)

Per-clip content. References corpus_map for metadata.

```json
{
  "clips": [
    {
      "system_clip_id": "3b1b_nn_1_neurons_3",
      "transcript": "[0.00s -> 3.20s] So if you think about it...",
      "caption": "The video shows a presenter at a whiteboard...",
      "transcript_is_empty": false
    }
  ]
}
```

**Where to hook:** Parse the chunk content fields (which contain `Caption:\n{caption}\nTranscript:\n{transcript}` pairs) and split them back out per clip. The `video_segments._data[video_name][index]` structure has the relevant fields if accessed directly.

## 1.3 Chunks (`indexing/chunks.json`)

Per-chunk content with explicit corpus tracing.

```json
{
  "chunks": [
    {
      "chunk_id": "chunk-abc123",
      "content": "Caption:\n...\nTranscript:\n...\n\nCaption:\n...",
      "token_count": 987,
      "chunk_order_index": 2,
      "constituent_clips": [
        {
          "system_clip_id": "3b1b_nn_1_neurons_3",
          "video_name": "3b1b_nn_1_neurons",
          "start_timestamp": "0:01:30",
          "end_timestamp": "0:02:00"
        }
      ]
    }
  ]
}
```

**Where to hook:** Iterate over `text_chunks_db` after indexing. For each chunk, the `video_segment_id` field lists clip IDs that contributed. Resolve each clip ID against corpus_map to enrich with timestamps.

## 1.4 Entities (`indexing/entities.json`)

Every entity in the knowledge graph with explicit corpus tracing.

```json
{
  "entities": [
    {
      "entity_name": "GRADERS",
      "entity_type": "CONCEPT",
      "description": "Evaluation tools used in...",
      "description_was_synthesized": true,
      "description_contains_sep_marker": false,
      "node_degree": 4,
      "source_chunks": [
        {
          "chunk_id": "chunk-abc123",
          "constituent_clips": [
            {
              "system_clip_id": "3b1b_nn_2_gradient_7",
              "video_name": "3b1b_nn_2_gradient",
              "start_timestamp": "0:03:30",
              "end_timestamp": "0:04:00"
            }
          ]
        }
      ],
      "videos_touched": ["3b1b_nn_2_gradient", "3b1b_nn_1_neurons"]
    }
  ]
}
```

**Where to hook:** Iterate over NetworkX graph nodes. For each node, read its attributes (entity_type, description, source_id, etc). Split source_id on `<SEP>` to get chunk IDs. For each chunk ID, look up the chunk and its constituent clips. Aggregate distinct videos.

**`description_was_synthesized` detection:** If the description contains the `<SEP>` marker (`<SEP>` literal), synthesis did NOT run (description is raw concatenation). If it doesn't contain `<SEP>` AND the entity has multiple source chunks, synthesis ran. If it has only one source chunk, synthesis was not applicable.

## 1.5 Relationships (`indexing/relationships.json`)

Every edge in the graph with corpus tracing.

```json
{
  "relationships": [
    {
      "source": "GRADERS",
      "target": "REINFORCEMENT FINE-TUNING",
      "description": "Graders are used as evaluation tools...",
      "description_was_synthesized": false,
      "weight": 17.0,
      "order": 1,
      "source_chunks": [
        {
          "chunk_id": "chunk-abc123",
          "video_name": "3b1b_nn_2_gradient",
          "constituent_clips": ["..."]
        }
      ],
      "videos_touched": ["3b1b_nn_2_gradient"]
    }
  ]
}
```

**Where to hook:** Iterate over NetworkX graph edges. Same enrichment pattern as entities.

## 1.6 Graph Summary (`indexing/graph_summary.json`)

Diagnostic dashboard for the graph at a glance.

```json
{
  "totals": {
    "nodes": 1247,
    "edges": 3891,
    "videos_indexed": 6,
    "clips": 234,
    "chunks": 89
  },
  "entity_type_distribution": {
    "CONCEPT": 412,
    "PERSON": 87,
    "ORGANIZATION": 45,
    "UNKNOWN": 23
  },
  "unknown_placeholder_count": 23,
  "node_degree_stats": {
    "min": 0,
    "max": 47,
    "median": 2,
    "mean": 6.2,
    "histogram_buckets": {"0-1": 312, "2-5": 489, "6-10": 287, "11+": 159}
  },
  "source_chunks_per_entity_stats": {
    "min": 1, "max": 23, "median": 1, "mean": 2.1
  },
  "synthesis_trigger_rate": {
    "entities_with_synthesis": 89,
    "entities_without_synthesis": 1158,
    "rate": 0.071
  },
  "description_length_stats": {
    "entities": {"min": 12, "max": 1842, "median": 87, "mean": 134},
    "edges": {"min": 18, "max": 521, "median": 76, "mean": 92}
  }
}
```

**Where to hook:** Compute from entities.json and relationships.json after they're built. Pure aggregation.

## 1.7 Provenance Check (`indexing/provenance_check.json`)

Verify that the index is internally consistent. Sample 20 entities and walk their provenance back to source.

```json
{
  "sample_size": 20,
  "checks_passed": 19,
  "checks_failed": 1,
  "failures": [
    {
      "entity_name": "EXAMPLE",
      "issue": "source_chunk 'chunk-xyz' referenced but not found in text_chunks_db"
    }
  ]
}
```

**Where to hook:** Sample entities. For each, walk source_id → chunks → constituent clips. Verify each link resolves. Report any breaks.

## 1.8 Sub-Graph Samples (`indexing/subgraph_samples/chunk_<id>/`)

For 10 sampled chunks, capture the LLM extraction stage in detail. **This requires hooks added during indexing**, not after.

Pick chunks diversely: 2-3 from start of corpus, 2-3 from middle, 2-3 from end, 1-2 from chunks producing many entities, 1-2 from chunks producing few entities.

For each sampled chunk:

**`raw_llm_response.txt`** — the exact string returned from `use_llm_func(hint_prompt)`. If gleaning ran multiple iterations, concatenate them with clear separators:

```
=== Initial extraction ===
("entity"<|>"GRADERS"<|>...)##...

=== Gleaning iteration 1 ===
("entity"<|>"SCORING SYSTEM"<|>...)##...

=== Loop check 1 response ===
yes

=== Gleaning iteration 2 ===
...
```

**`parsed_subgraph.json`** — the `maybe_nodes` and `maybe_edges` dicts after parsing but before merging:

```json
{
  "chunk_id": "chunk-abc123",
  "parsed_entities": {
    "GRADERS": [
      {"entity_name": "GRADERS", "entity_type": "CONCEPT", "description": "...", "source_id": "chunk-abc123"}
    ]
  },
  "parsed_relationships": {
    "[GRADERS, REINFORCEMENT FINE-TUNING]": [
      {"src_id": "GRADERS", "tgt_id": "REINFORCEMENT FINE-TUNING", "weight": 9.0, "description": "..."}
    ]
  },
  "stats": {
    "entities_extracted": 7,
    "relationships_extracted": 5,
    "gleaning_iterations": 2,
    "parsing_failures": 0
  }
}
```

**`chunk_corpus_info.json`** — what this chunk corresponds to in the corpus:

```json
{
  "chunk_id": "chunk-abc123",
  "constituent_clips": [...]
}
```

**Where to hook:** In `_op.py`, `extract_entities._process_single_content`. After `final_result = await use_llm_func(hint_prompt)` and after the gleaning loop, write the raw response. After the parsing loop (which produces `maybe_nodes` and `maybe_edges` locally), write the parsed subgraph. Decide whether to sample this chunk based on a sample list passed in via config.

## 1.9 Merge Traces (`indexing/merge_traces/entity_<NAME>/`)

For 30 sampled entities, capture the merging process in detail. **This requires hooks added during indexing.**

Sample entities diversely: 10 high-degree entities, 10 low-degree (degree 1-2), 5 that triggered synthesis, 5 that didn't.

For each sampled entity:

**`merge_group.json`** — what went into the merge:

```json
{
  "entity_name": "GRADERS",
  "extractions_before_merge": [
    {
      "from_chunk": "chunk-abc123",
      "extracted_type": "CONCEPT",
      "extracted_description": "Evaluation tools used in..."
    },
    {
      "from_chunk": "chunk-def456",
      "extracted_type": "TECHNOLOGY",
      "extracted_description": "Automated evaluation components..."
    }
  ],
  "already_existed_in_graph": false
}
```

**`resolution.json`** — what merging decided:

```json
{
  "entity_name": "GRADERS",
  "type_resolution": {
    "vote_counts": {"CONCEPT": 3, "TECHNOLOGY": 1},
    "winning_type": "CONCEPT"
  },
  "description_resolution": {
    "joined_description_token_count": 145,
    "synthesis_threshold": 100,
    "synthesis_triggered": true,
    "description_before_synthesis": "Evaluation tools used in...<SEP>Automated evaluation components...",
    "description_after_synthesis": "Graders are automated evaluation tools used in..."
  },
  "source_id_union": ["chunk-abc123", "chunk-def456", "chunk-ghi789"]
}
```

**`corpus_trace.json`** — what corpus content this entity touches:

```json
{
  "entity_name": "GRADERS",
  "videos_touched": ["3b1b_nn_2_gradient"],
  "clip_appearances": [
    {"system_clip_id": "3b1b_nn_2_gradient_7", "timestamp": "0:03:30-0:04:00"},
    {"system_clip_id": "3b1b_nn_2_gradient_8", "timestamp": "0:04:00-0:04:30"}
  ]
}
```

**Where to hook:** In `_op.py`, `_merge_nodes_then_upsert`. Before the merging operations (Counter for type, GRAPH_FIELD_SEP join for description), capture the inputs. Inside `_handle_entity_relation_summary`, capture whether synthesis triggered and the before/after descriptions.

## 1.10 Aggregate Stats (`indexing/aggregate_stats.json`)

Stats across all chunks/entities (not just sampled). Cheap to compute.

```json
{
  "extractions_per_chunk": {
    "entity_counts": {"min": 0, "max": 23, "median": 5, "mean": 6.1},
    "relationship_counts": {"min": 0, "max": 18, "median": 3, "mean": 4.2},
    "chunks_with_zero_extractions": 3,
    "chunks_with_parsing_failures": 0
  },
  "merge_group_size_distribution": {
    "size_1": 891,
    "size_2": 234,
    "size_3-5": 87,
    "size_6-10": 28,
    "size_11+": 7
  },
  "synthesis_trigger_rate": {
    "entities_above_threshold": 89,
    "total_entities": 1247
  }
}
```

**Where to hook:** Track counts during indexing. Either via hooks in extraction/merging, or by post-processing the captured outputs.

---

# Part 2: Retrieval Outputs

These come from instrumenting `videorag_query` in `_op.py`. One folder per query.

## 2.1 Query (`queries/q<NNN>/query.json`)

```json
{
  "query_id": "q001",
  "query_text": "How does the structure of neurons relate to backpropagation?",
  "query_metadata": {
    "expected_clips": ["3b1b_nn_1_neurons_5", "3b1b_nn_2_gradient_8"],
    "expected_videos": ["3b1b_nn_1_neurons", "3b1b_nn_2_gradient"],
    "query_type": "cross-video|factual|pedagogical|adversarial",
    "expected_behavior_notes": "Pre-run notes from the human evaluator"
  }
}
```

**Where to hook:** Save at the start of `videorag_query`. The metadata fields come from the eval_set.json (passed in via config or merged afterwards).

## 2.2 Reformulations (`queries/q<NNN>/reformulations.json`)

```json
{
  "original_query": "How does the structure...",
  "entity_retrieval_query": "The structure of neurons relates to backpropagation.",
  "visual_retrieval_query": "A diagram showing neurons connected in layers with computation flowing backwards.",
  "extracted_keywords": ["structure", "neurons", "backpropagation", "layers"]
}
```

**Where to hook:** After `_refine_entity_retrieval_query`, `_refine_visual_retrieval_query`, and `_extract_keywords_query` calls.

## 2.3 Path 1 (`queries/q<NNN>/path1.json`)

```json
{
  "reformulated_query": "...",
  "retrieved_entities": [
    {
      "entity_name": "NEURON",
      "similarity_score": 0.823,
      "entity_type": "CONCEPT",
      "description": "...",
      "node_degree": 12,
      "source_chunks": ["chunk-abc", "chunk-def"]
    }
  ],
  "entities_below_cutoff": [
    {"entity_name": "WEIGHT", "similarity_score": 0.198}
  ],
  "one_hop_neighbors": {
    "NEURON": ["LAYER", "ACTIVATION", "WEIGHT", "BIAS"],
    "BACKPROPAGATION": ["GRADIENT", "CHAIN RULE", "DERIVATIVE"]
  },
  "chunk_scoring": [
    {
      "chunk_id": "chunk-abc",
      "relation_counts": 4,
      "constituent_clips": [
        {"system_clip_id": "3b1b_nn_1_neurons_5", "timestamp": "0:02:30-0:03:00"}
      ]
    }
  ],
  "retrieved_clip_ids": ["3b1b_nn_1_neurons_5", "3b1b_nn_2_gradient_8"]
}
```

**Where to hook:** Inside `videorag_query`, after the entity_vdb query and `_find_most_related_segments_from_entities` call. The `entities_below_cutoff` requires fetching slightly more than top-K (e.g., top-K+5) to see what just missed.

## 2.4 Path 2 (`queries/q<NNN>/path2.json`)

```json
{
  "visual_scene_query": "...",
  "retrieved_clips": [
    {
      "system_clip_id": "3b1b_nn_1_neurons_5",
      "similarity_score": 0.654,
      "video_name": "3b1b_nn_1_neurons",
      "timestamp": "0:02:30-0:03:00"
    }
  ],
  "clips_below_cutoff": [
    {"system_clip_id": "...", "similarity_score": 0.198}
  ]
}
```

**Where to hook:** After the visual_segment_feature_vdb query. Enrich clip IDs with timestamps from corpus_map.

## 2.5 Path 3 (`queries/q<NNN>/path3.json`)

```json
{
  "original_query": "...",
  "retrieved_chunks": [
    {
      "chunk_id": "chunk-abc",
      "similarity_score": 0.734,
      "content": "Caption:\n...",
      "constituent_clips": [
        {"system_clip_id": "3b1b_nn_1_neurons_5", "timestamp": "0:02:30-0:03:00"}
      ],
      "was_truncated_out": false
    }
  ],
  "chunks_truncated_out": [
    {"chunk_id": "chunk-xyz", "reason": "exceeded naive_max_token_for_text_unit"}
  ]
}
```

**Where to hook:** After `chunks_vdb.query` and `truncate_list_by_token_size`. Compare full retrieved list against truncated list to populate `chunks_truncated_out`.

## 2.6 Filter (`queries/q<NNN>/filter.json`)

```json
{
  "union_of_paths_1_and_2": ["3b1b_nn_1_neurons_5", "3b1b_nn_2_gradient_8", "..."],
  "filter_decisions": [
    {
      "system_clip_id": "3b1b_nn_1_neurons_5",
      "rough_caption": "The presenter shows...",
      "filter_response": "Yes, this segment discusses neuron structure...",
      "parsed_decision": "yes",
      "kept": true
    }
  ],
  "clips_after_filter": ["3b1b_nn_1_neurons_5", "3b1b_nn_2_gradient_8"],
  "fallback_triggered": false
}
```

**Where to hook:** Inside the `_filter_single_segment` loop. After `await asyncio.gather`, before the `remain_segments` assignment.

## 2.7 Re-caption (`queries/q<NNN>/recaption.json`)

```json
{
  "keywords_injected": ["structure", "neurons", "backpropagation"],
  "recaptions": [
    {
      "system_clip_id": "3b1b_nn_1_neurons_5",
      "video_name": "3b1b_nn_1_neurons",
      "timestamp": "0:02:30-0:03:00",
      "transcript_used": "...",
      "frames_sampled": 15,
      "recaption": "The video shows a neural network with...",
      "indexing_time_caption": "The presenter explains..."
    }
  ]
}
```

**Where to hook:** After `retrieved_segment_caption` call. Pair each clip's re-caption with its original indexing-time caption for comparison.

## 2.8 Generation (`queries/q<NNN>/generation.json`)

```json
{
  "video_data_csv": "video_name,start_time,end_time,content\n...",
  "chunk_data_text": "Caption:\n...\n-----New Chunk-----\nCaption:\n...",
  "full_system_prompt": "---Role---\n...",
  "response": "Neurons are described as...",
  "token_counts": {
    "input_tokens": 4521,
    "output_tokens": 687
  }
}
```

**Where to hook:** After `use_model_func` final call. Capture the assembled `sys_prompt` (post-substitution) and the response. Token counts come from the API response object.

## 2.9 Timing (`queries/q<NNN>/timing.json`)

```json
{
  "total_seconds": 23.4,
  "stages": {
    "path1_reformulation": 0.8,
    "path1_entity_match": 0.3,
    "path1_chunk_scoring": 0.1,
    "path2_reformulation": 0.7,
    "path2_visual_match": 0.5,
    "path3_chunk_retrieval": 0.2,
    "filtering": 8.2,
    "keyword_extraction": 0.6,
    "recaptioning": 11.4,
    "generation": 0.6
  }
}
```

**Where to hook:** Wrap each major step in time.time() measurements.

---

# Part 3: Implementation Approach

## 3.1 Configuration

Add a config option `analysis_output_dir` to the global config. When set to a path, instrumentation is active. When None or unset, no instrumentation runs (zero overhead).

For sub-graph sampling, add `subgraph_sample_chunk_ids` (a list of chunk IDs to instrument fully). Same for entities: `merge_trace_entity_names`.

These sample lists can be:
1. Set explicitly by the user before indexing
2. Determined by a small "sampling planner" function that picks diverse chunks based on simple heuristics (e.g., spread across video files, mix of high and low extraction counts)

## 3.2 Hook Pattern

Instrumentation should be small, isolated functions that write to disk. Example pattern:

```python
def _dump_analysis(subdir: str, filename: str, data: dict | str, output_dir: Path | None):
    """Write analysis output to disk. No-op if output_dir is None."""
    if output_dir is None:
        return
    target = output_dir / subdir
    target.mkdir(parents=True, exist_ok=True)
    target_file = target / filename
    if isinstance(data, str):
        target_file.write_text(data)
    else:
        target_file.write_text(json.dumps(data, indent=2, default=str))
```

Then hook sites become single-line additions:

```python
final_result = await use_llm_func(hint_prompt)
_dump_analysis(f"subgraph_samples/chunk_{chunk_key}", "raw_llm_response.txt", final_result, analysis_dir)
```

## 3.3 Two Scripts to Create

**`scripts/extract_indexing_analysis.py`** — runs AFTER indexing completes. Reads from existing storage (text_chunks_db JSON, NetworkX graph file, VDB files) and produces sections 1.1-1.7 and 1.10. No re-running of expensive operations.

For sections 1.8 and 1.9 (sub-graph samples and merge traces), these require hooks DURING indexing. So either:
- (a) Add hooks to `_op.py` that activate when `analysis_output_dir` is set, and re-run indexing once with instrumentation
- (b) Skip 1.8 and 1.9 if re-indexing is too expensive, and document them as "would-be-useful but requires re-indexing"

Recommendation: implement (a) so future runs benefit, but make the hooks conditional on config so existing behavior is preserved when analysis is off.

**`scripts/run_query_with_analysis.py`** — wraps `videorag_query` with full instrumentation. Loads `eval_set.json`, runs each query, dumps all section 2 outputs per query.

## 3.4 What NOT to Capture

Skip these to keep things manageable:
- Raw embedding vectors (recomputable, large)
- Raw API response objects (the structured outputs are sufficient)
- Anything derivable from other captured outputs (don't store both raw counts and percentages)

---

# Part 4: Validation

After implementation, verify the instrumentation by running:

1. **Indexing analysis extraction** on the existing index. Verify all files in `videorag_analysis/indexing/` exist and validate against schema.

2. **One test query** with full instrumentation. Verify `videorag_analysis/queries/q_test/` contains all 9 expected files (query, reformulations, path1-3, filter, recaption, generation, timing).

3. **Provenance round-trip check.** Pick a random entity from `entities.json`. Follow its `source_chunks` → look up each chunk in `chunks.json` → look up each constituent clip in `corpus_map.json` → verify the timestamps are sensible. This catches broken provenance threading.

4. **Behavioral invariance check.** Run a query with `analysis_output_dir=None` and the same query with instrumentation enabled. The generated response should be identical (or near-identical, accounting for any non-determinism). Instrumentation must not change pipeline behavior.