"""Offline extraction of indexing-stage analysis outputs.

Reads the VideoRAG index storage on disk and produces the analysis JSON
files specified in notes/videorag_analysis_spec.md sections 1.1-1.7 and 1.10.
No model calls — pure post-processing of files already written by indexing.

Sections 1.8 (subgraph_samples/) and 1.9 (merge_traces/) are produced
inline during indexing by the hooks in videorag/_op.py — not here.

Usage:
    python scripts/extract_indexing_analysis.py \\
        --workdir /content/videorag_workdir \\
        --output-dir /content/videorag_analysis/indexing \\
        [--config-name deepseek_bge_config] \\
        [--provenance-sample-size 20]
"""

import argparse
import json
import random
import statistics
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import networkx as nx


# Source of truth: videorag/prompt.py
GRAPH_FIELD_SEP = "<SEP>"

# Metadata bundled with each config name. Extend as new configs are added.
KNOWN_CONFIGS: Dict[str, dict] = {
    "deepseek_bge_config": {
        "llm_models": {"best": "deepseek-chat", "cheap": "deepseek-chat"},
        "embedding_model": "BAAI/bge-m3",
        "visual_encoder": "ImageBind",
        "vlm": "MiniCPM-V-2_6-int4",
        "asr_model": "faster-distil-whisper-large-v3",
    },
    "openai_config": {
        "llm_models": {"best": "gpt-4o", "cheap": "gpt-4o-mini"},
        "embedding_model": "text-embedding-3-small",
        "visual_encoder": "ImageBind",
        "vlm": "MiniCPM-V-2_6-int4",
        "asr_model": "faster-distil-whisper-large-v3",
    },
}


# ─── helpers ────────────────────────────────────────────────────────────


def fmt_timestamp(seconds: float) -> str:
    """Seconds -> H:MM:SS string (matches the format videorag_query emits)."""
    s = int(seconds)
    h = s // 3600
    m = (s % 3600) // 60
    s = s % 60
    return f"{h}:{m:02d}:{s:02d}"


def split_caption_transcript(content: str) -> Tuple[str, str]:
    """Split a clip's content field into (caption, transcript).

    Content is written by merge_segment_information as:
        "Caption:\\n{caption}\\nTranscript:\\n{transcript}\\n\\n"
    """
    parts = content.split("\nTranscript:\n", 1)
    caption = parts[0]
    if caption.startswith("Caption:\n"):
        caption = caption[len("Caption:\n") :]
    transcript = parts[1] if len(parts) > 1 else ""
    return caption.rstrip(), transcript.rstrip()


def derive_synthesis_state(
    description: str, source_chunk_count: int
) -> Tuple[bool, bool]:
    """Return (description_was_synthesized, description_contains_sep_marker).

    Heuristic per spec 1.4:
      - contains <SEP> → not synthesized (raw concatenation survived)
      - no <SEP> AND multiple source chunks → synthesized
      - no <SEP> AND single source chunk → not applicable; reported as False
    """
    contains_sep = GRAPH_FIELD_SEP in description
    was_synthesized = (not contains_sep) and source_chunk_count > 1
    return was_synthesized, contains_sep


def stats_block(values: List[float]) -> dict:
    if not values:
        return {"min": 0, "max": 0, "median": 0, "mean": 0.0}
    return {
        "min": min(values),
        "max": max(values),
        "median": statistics.median(values),
        "mean": round(statistics.mean(values), 2),
    }


def degree_histogram(values: List[int]) -> dict:
    buckets = {"0-1": 0, "2-5": 0, "6-10": 0, "11+": 0}
    for v in values:
        if v <= 1:
            buckets["0-1"] += 1
        elif v <= 5:
            buckets["2-5"] += 1
        elif v <= 10:
            buckets["6-10"] += 1
        else:
            buckets["11+"] += 1
    return buckets


def merge_size_bucket(size: int) -> str:
    if size == 1:
        return "size_1"
    if size == 2:
        return "size_2"
    if size <= 5:
        return "size_3-5"
    if size <= 10:
        return "size_6-10"
    return "size_11+"


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, default=str, ensure_ascii=False),
        encoding="utf-8",
    )


# ─── loaders ────────────────────────────────────────────────────────────


REQUIRED_FILES = [
    "kv_store_video_path.json",
    "kv_store_video_segments.json",
    "kv_store_text_chunks.json",
    "graph_chunk_entity_relation.graphml",
]


def load_workdir(workdir: Path) -> dict:
    missing = [n for n in REQUIRED_FILES if not (workdir / n).exists()]
    if missing:
        raise FileNotFoundError(
            "Missing required index files in workdir "
            f"{workdir}: {missing}. Has indexing completed successfully?"
        )

    def _load_json(name: str) -> dict:
        with (workdir / name).open(encoding="utf-8") as f:
            return json.load(f)

    return {
        "video_path": _load_json("kv_store_video_path.json"),
        "video_segments": _load_json("kv_store_video_segments.json"),
        "text_chunks": _load_json("kv_store_text_chunks.json"),
        "graphml_path": workdir / "graph_chunk_entity_relation.graphml",
    }


# ─── section builders ───────────────────────────────────────────────────


def build_corpus_map(data: dict, config_name: Optional[str]) -> dict:
    metadata_extras = KNOWN_CONFIGS.get(config_name, {}) if config_name else {}
    indexed_at = datetime.fromtimestamp(
        data["graphml_path"].stat().st_mtime
    ).isoformat()
    indexing_metadata = {
        "indexed_at": indexed_at,
        "config_name": config_name or "unknown",
        **metadata_extras,
    }

    videos = []
    clips = []
    for video_name, segments in data["video_segments"].items():
        end_seconds_max = 0.0
        for clip_idx_str, clip in segments.items():
            start_str, end_str = clip["time"].split("-")
            start_s = float(start_str)
            end_s = float(end_str)
            end_seconds_max = max(end_seconds_max, end_s)
            clips.append(
                {
                    "system_clip_id": f"{video_name}_{clip_idx_str}",
                    "video_name": video_name,
                    "video_file_path": data["video_path"].get(video_name, ""),
                    "clip_index": int(clip_idx_str),
                    "start_seconds": start_s,
                    "end_seconds": end_s,
                    "start_timestamp": fmt_timestamp(start_s),
                    "end_timestamp": fmt_timestamp(end_s),
                    "duration_seconds": round(end_s - start_s, 3),
                    "sampled_frame_times": clip.get("frame_times", []),
                }
            )
        videos.append(
            {
                "video_name": video_name,
                "file_path": data["video_path"].get(video_name, ""),
                "duration_seconds": end_seconds_max,
                "duration_timestamp": fmt_timestamp(end_seconds_max),
                "num_clips": len(segments),
            }
        )
    return {"indexing_metadata": indexing_metadata, "videos": videos, "clips": clips}


def build_clip_lookup(corpus_map: dict) -> dict:
    """Index corpus_map.clips by system_clip_id for cheap enrichment lookups."""
    return {
        c["system_clip_id"]: {
            "video_name": c["video_name"],
            "start_timestamp": c["start_timestamp"],
            "end_timestamp": c["end_timestamp"],
        }
        for c in corpus_map["clips"]
    }


def build_clips_json(data: dict) -> dict:
    out = []
    for video_name, segments in data["video_segments"].items():
        for clip_idx_str, clip in segments.items():
            content = clip.get("content", "")
            # Prefer the dedicated transcript field where present (more reliable
            # than re-parsing content), but fall back to content parsing.
            stored_transcript = clip.get("transcript")
            if stored_transcript is not None:
                caption, _ = split_caption_transcript(content)
                transcript = stored_transcript
            else:
                caption, transcript = split_caption_transcript(content)
            out.append(
                {
                    "system_clip_id": f"{video_name}_{clip_idx_str}",
                    "transcript": transcript,
                    "caption": caption,
                    "transcript_is_empty": len(transcript.strip()) == 0,
                }
            )
    return {"clips": out}


def build_chunks_json(data: dict, clip_lookup: dict) -> dict:
    chunks = []
    for chunk_id, chunk in data["text_chunks"].items():
        constituent = []
        for clip_id in chunk.get("video_segment_id", []):
            info = clip_lookup.get(clip_id)
            if info is None:
                constituent.append({"system_clip_id": clip_id, "missing": True})
            else:
                constituent.append(
                    {
                        "system_clip_id": clip_id,
                        "video_name": info["video_name"],
                        "start_timestamp": info["start_timestamp"],
                        "end_timestamp": info["end_timestamp"],
                    }
                )
        chunks.append(
            {
                "chunk_id": chunk_id,
                "content": chunk.get("content", ""),
                "token_count": chunk.get("tokens", 0),
                "chunk_order_index": chunk.get("chunk_order_index", 0),
                "constituent_clips": constituent,
            }
        )
    return {"chunks": chunks}


def build_entities_json(
    graph: nx.Graph, chunk_lookup: dict, clip_lookup: dict
) -> dict:
    entities = []
    for node_id, attrs in graph.nodes(data=True):
        source_id = attrs.get("source_id", "") or ""
        source_chunk_ids = [s for s in source_id.split(GRAPH_FIELD_SEP) if s]
        description = attrs.get("description", "") or ""
        was_synth, has_sep = derive_synthesis_state(description, len(source_chunk_ids))

        source_chunks = []
        videos_touched = set()
        for cid in source_chunk_ids:
            chunk = chunk_lookup.get(cid)
            if chunk is None:
                source_chunks.append(
                    {"chunk_id": cid, "missing": True, "constituent_clips": []}
                )
                continue
            constituent = []
            for clip_id in chunk.get("video_segment_id", []):
                info = clip_lookup.get(clip_id)
                if info is None:
                    constituent.append({"system_clip_id": clip_id, "missing": True})
                else:
                    videos_touched.add(info["video_name"])
                    constituent.append(
                        {
                            "system_clip_id": clip_id,
                            "video_name": info["video_name"],
                            "start_timestamp": info["start_timestamp"],
                            "end_timestamp": info["end_timestamp"],
                        }
                    )
            source_chunks.append(
                {"chunk_id": cid, "constituent_clips": constituent}
            )

        entities.append(
            {
                "entity_name": node_id,
                "entity_type": attrs.get("entity_type", "") or "",
                "description": description,
                "description_was_synthesized": was_synth,
                "description_contains_sep_marker": has_sep,
                "node_degree": graph.degree(node_id),
                "source_chunks": source_chunks,
                "videos_touched": sorted(videos_touched),
            }
        )
    return {"entities": entities}


def build_relationships_json(
    graph: nx.Graph, chunk_lookup: dict, clip_lookup: dict
) -> dict:
    rels = []
    for u, v, attrs in graph.edges(data=True):
        source_id = attrs.get("source_id", "") or ""
        source_chunk_ids = [s for s in source_id.split(GRAPH_FIELD_SEP) if s]
        description = attrs.get("description", "") or ""
        was_synth, _ = derive_synthesis_state(description, len(source_chunk_ids))

        weight = attrs.get("weight", 1.0)
        try:
            weight = float(weight)
        except (TypeError, ValueError):
            weight = 1.0
        order = attrs.get("order", 1)
        try:
            order = int(order)
        except (TypeError, ValueError):
            order = 1

        source_chunks = []
        videos_touched = set()
        for cid in source_chunk_ids:
            chunk = chunk_lookup.get(cid)
            if chunk is None:
                source_chunks.append({"chunk_id": cid, "missing": True})
                continue
            constituent_ids = chunk.get("video_segment_id", [])
            chunk_videos = set()
            for clip_id in constituent_ids:
                info = clip_lookup.get(clip_id)
                if info is not None:
                    videos_touched.add(info["video_name"])
                    chunk_videos.add(info["video_name"])
            source_chunks.append(
                {
                    "chunk_id": cid,
                    "video_name": next(iter(chunk_videos), ""),
                    "constituent_clips": constituent_ids,
                }
            )

        rels.append(
            {
                "source": u,
                "target": v,
                "description": description,
                "description_was_synthesized": was_synth,
                "weight": weight,
                "order": order,
                "source_chunks": source_chunks,
                "videos_touched": sorted(videos_touched),
            }
        )
    return {"relationships": rels}


def build_graph_summary(
    entities_data: dict,
    relationships_data: dict,
    corpus_map: dict,
    chunks_data: dict,
) -> dict:
    entities = entities_data["entities"]
    relationships = relationships_data["relationships"]

    raw_types = [e["entity_type"] for e in entities]
    # Entity type strings often carry surrounding quote characters because the
    # extraction prompt emits them quoted (e.g. '"CONCEPT"'). Normalize for
    # the distribution and unknown count but keep the raw form in entities.json.
    norm = lambda t: (t or "").strip().strip('"').strip("'").upper()
    type_dist = Counter(norm(t) for t in raw_types)
    unknown_count = type_dist.get("UNKNOWN", 0)

    degrees = [e["node_degree"] for e in entities]
    src_chunk_counts = [len(e["source_chunks"]) for e in entities]
    synth_count = sum(1 for e in entities if e["description_was_synthesized"])
    no_synth_count = len(entities) - synth_count
    entity_desc_lens = [len(e["description"]) for e in entities]
    edge_desc_lens = [len(r["description"]) for r in relationships]

    return {
        "totals": {
            "nodes": len(entities),
            "edges": len(relationships),
            "videos_indexed": len(corpus_map["videos"]),
            "clips": len(corpus_map["clips"]),
            "chunks": len(chunks_data["chunks"]),
        },
        "entity_type_distribution": dict(type_dist),
        "unknown_placeholder_count": unknown_count,
        "node_degree_stats": {
            **stats_block(degrees),
            "histogram_buckets": degree_histogram(degrees),
        },
        "source_chunks_per_entity_stats": stats_block(src_chunk_counts),
        "synthesis_trigger_rate": {
            "entities_with_synthesis": synth_count,
            "entities_without_synthesis": no_synth_count,
            "rate": round(synth_count / len(entities), 4) if entities else 0.0,
        },
        "description_length_stats": {
            "entities": stats_block(entity_desc_lens),
            "edges": stats_block(edge_desc_lens),
        },
    }


def build_provenance_check(
    entities_data: dict,
    chunk_lookup: dict,
    clip_lookup: dict,
    sample_size: int,
) -> dict:
    """Sample N entities and walk source_chunks -> constituent_clips -> corpus.

    Reports breaks: missing chunks, missing clips. Uses a local seeded RNG
    so runs are reproducible.
    """
    entities = entities_data["entities"]
    if not entities:
        return {"sample_size": 0, "checks_passed": 0, "checks_failed": 0, "failures": []}

    sample_size = min(sample_size, len(entities))
    sampled = random.Random(0).sample(entities, sample_size)

    failures = []
    passed = 0
    for entity in sampled:
        issues: List[str] = []
        for sc in entity["source_chunks"]:
            if sc.get("missing"):
                issues.append(
                    f"source_chunk '{sc['chunk_id']}' referenced but not found "
                    "in text_chunks_db"
                )
                continue
            for clip in sc.get("constituent_clips", []):
                if clip.get("missing"):
                    issues.append(
                        f"constituent_clip '{clip['system_clip_id']}' referenced "
                        "from chunk but not found in video_segments"
                    )
        if issues:
            failures.append(
                {
                    "entity_name": entity["entity_name"],
                    "issue": "; ".join(issues),
                }
            )
        else:
            passed += 1

    return {
        "sample_size": sample_size,
        "checks_passed": passed,
        "checks_failed": len(failures),
        "failures": failures,
    }


def build_aggregate_stats(
    entities_data: dict,
    relationships_data: dict,
    chunks_data: dict,
) -> dict:
    """Aggregations derivable from post-index storage."""
    chunk_ids = {c["chunk_id"] for c in chunks_data["chunks"]}
    entities_per_chunk = Counter()
    rels_per_chunk = Counter()

    for entity in entities_data["entities"]:
        for sc in entity["source_chunks"]:
            entities_per_chunk[sc["chunk_id"]] += 1
    for rel in relationships_data["relationships"]:
        for sc in rel["source_chunks"]:
            rels_per_chunk[sc["chunk_id"]] += 1

    entity_counts = [entities_per_chunk.get(c, 0) for c in chunk_ids]
    rel_counts = [rels_per_chunk.get(c, 0) for c in chunk_ids]

    merge_sizes = [len(e["source_chunks"]) for e in entities_data["entities"]]
    merge_bucket_counts: Dict[str, int] = {
        "size_1": 0,
        "size_2": 0,
        "size_3-5": 0,
        "size_6-10": 0,
        "size_11+": 0,
    }
    for size in merge_sizes:
        if size == 0:
            continue
        merge_bucket_counts[merge_size_bucket(size)] += 1

    synth_count = sum(
        1 for e in entities_data["entities"] if e["description_was_synthesized"]
    )

    return {
        "extractions_per_chunk": {
            "entity_counts": stats_block(entity_counts),
            "relationship_counts": stats_block(rel_counts),
            "chunks_with_zero_extractions": sum(1 for v in entity_counts if v == 0),
            # parsing_failures is captured only on the sampled-chunk path in
            # _op.py and is not aggregated across all chunks at index time.
            # Read parsed_subgraph.json files under subgraph_samples/ for that.
            "chunks_with_parsing_failures": None,
        },
        "merge_group_size_distribution": merge_bucket_counts,
        "synthesis_trigger_rate": {
            "entities_above_threshold": synth_count,
            "total_entities": len(entities_data["entities"]),
        },
        "_notes": {
            "chunks_with_parsing_failures": (
                "Null because post-index storage does not retain per-chunk parse "
                "counts. For sampled chunks see subgraph_samples/*/parsed_subgraph.json."
            )
        },
    }


# ─── driver ─────────────────────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--workdir", required=True, type=Path,
                   help="VideoRAG index directory (the working_dir passed to VideoRAG()).")
    p.add_argument("--output-dir", required=True, type=Path,
                   help="Where to write the analysis JSON files (typically videorag_analysis/indexing/).")
    p.add_argument("--config-name", default="deepseek_bge_config",
                   choices=sorted(KNOWN_CONFIGS.keys()),
                   help="Which config the index was built with. Used only to populate "
                        "indexing_metadata; not all configs have metadata defined.")
    p.add_argument("--provenance-sample-size", type=int, default=20,
                   help="How many entities to spot-check in provenance_check.json.")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    workdir = args.workdir.resolve()
    output_dir = args.output_dir.resolve()

    print(f"Reading workdir: {workdir}", file=sys.stderr)
    data = load_workdir(workdir)
    graph = nx.read_graphml(str(data["graphml_path"]))
    print(
        f"Loaded graph: {graph.number_of_nodes()} nodes, "
        f"{graph.number_of_edges()} edges",
        file=sys.stderr,
    )

    print(f"Writing analysis to: {output_dir}", file=sys.stderr)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Build in dependency order so each step can reuse the previous outputs.
    corpus_map = build_corpus_map(data, args.config_name)
    write_json(output_dir / "corpus_map.json", corpus_map)

    clip_lookup = build_clip_lookup(corpus_map)

    clips_data = build_clips_json(data)
    write_json(output_dir / "clips.json", clips_data)

    chunks_data = build_chunks_json(data, clip_lookup)
    write_json(output_dir / "chunks.json", chunks_data)
    chunk_lookup = {c["chunk_id"]: data["text_chunks"][c["chunk_id"]] for c in chunks_data["chunks"]}

    entities_data = build_entities_json(graph, chunk_lookup, clip_lookup)
    write_json(output_dir / "entities.json", entities_data)

    relationships_data = build_relationships_json(graph, chunk_lookup, clip_lookup)
    write_json(output_dir / "relationships.json", relationships_data)

    graph_summary = build_graph_summary(
        entities_data, relationships_data, corpus_map, chunks_data
    )
    write_json(output_dir / "graph_summary.json", graph_summary)

    provenance = build_provenance_check(
        entities_data, chunk_lookup, clip_lookup, args.provenance_sample_size
    )
    write_json(output_dir / "provenance_check.json", provenance)

    aggregate = build_aggregate_stats(entities_data, relationships_data, chunks_data)
    write_json(output_dir / "aggregate_stats.json", aggregate)

    print(
        "Wrote 8 analysis files: corpus_map, clips, chunks, entities, "
        "relationships, graph_summary, provenance_check, aggregate_stats",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
