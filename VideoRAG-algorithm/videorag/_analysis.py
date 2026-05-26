"""Instrumentation helpers for dumping intermediate pipeline outputs to disk.

All functions in this module are no-ops when output_dir is None — pipeline
behavior must be unchanged whether analysis instrumentation is on or off.
"""

import json
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union


def dump_analysis(
    subdir: str,
    filename: str,
    data: Union[dict, list, str],
    output_dir: Union[str, Path, None],
) -> None:
    """Write analysis output to disk. No-op if output_dir is None.

    JSON is pretty-printed with indent=2 and default=str so non-serializable
    objects (Path, set, numpy scalars, etc.) fall back to their str() form.
    Strings are written verbatim and are used for raw LLM responses.
    """
    if output_dir is None:
        return
    target = Path(output_dir) / subdir
    target.mkdir(parents=True, exist_ok=True)
    target_file = target / filename
    if isinstance(data, str):
        target_file.write_text(data, encoding="utf-8")
    else:
        target_file.write_text(
            json.dumps(data, indent=2, default=str, ensure_ascii=False),
            encoding="utf-8",
        )


def sanitize_for_path(name: str) -> str:
    """Make an arbitrary string safe for use as a directory or file name.

    Entity names like 'REINFORCEMENT FINE-TUNING' or 'Operation: Dulce' contain
    spaces, colons and other characters that some filesystems reject. Replace
    anything outside [A-Za-z0-9-_.] with '_', collapse runs of underscores,
    and strip leading/trailing underscores.
    """
    safe = "".join(c if (c.isalnum() or c in "-._") else "_" for c in name)
    while "__" in safe:
        safe = safe.replace("__", "_")
    return safe.strip("_") or "unnamed"


def plan_chunk_samples(chunks: Dict[str, dict], target: int = 10) -> List[str]:
    """Pick chunk IDs for sub-graph sampling by even spread across the corpus.

    Spec 1.8 calls for '2-3 from start, 2-3 from middle, 2-3 from end' plus
    '1-2 from chunks producing many/few entities'. The latter requires
    knowing extraction counts, which haven't been produced at plan time.
    We therefore pick `target` evenly-spaced positions across the chunks
    dict; this naturally covers start, middle and end without needing
    explicit thirds. Order-dependent: relies on insertion-order iteration
    of the chunks dict, which reflects video-then-chunk-order at index
    construction time.
    """
    keys = list(chunks.keys())
    n = len(keys)
    if n == 0:
        return []
    if n <= target:
        return keys
    step = n / target
    picks = [keys[min(int(i * step), n - 1)] for i in range(target)]
    # Defensive dedupe — even spacing on tiny corpora can collide.
    seen = set()
    out = []
    for k in picks:
        if k not in seen:
            seen.add(k)
            out.append(k)
    return out


def plan_entity_samples(
    maybe_nodes: Dict[str, list],
    summary_max_tokens: int,
    tiktoken_model_name: str,
    target: int = 30,
) -> List[str]:
    """Pick entity names for merge tracing using proxies available pre-merge.

    Spec 1.9 calls for '10 high-degree, 10 low-degree, 5 that triggered
    synthesis, 5 that didn't'. Those are post-merge attributes. Proxies:
      - extraction count (len(extractions) per name) ~ high/low degree
      - distinct entity_type votes among extractions ~ interesting merges
      - joined-description token count >= summary_max_tokens ~ synthesis triggers

    Runs once after all chunks have been parsed but before merging starts.
    Deterministic given identical inputs (relies on dict insertion order
    and stable sorted() ties).
    """
    if not maybe_nodes:
        return []

    # Lazy imports — keep dump_analysis/sanitize_for_path usable in contexts
    # where tiktoken or the rest of the package isn't loaded.
    from ._utils import encode_string_by_tiktoken
    from .prompt import GRAPH_FIELD_SEP

    by_count_desc = sorted(maybe_nodes.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    high_degree = [name for name, _ in by_count_desc[:10]]
    low_degree = [name for name, exts in maybe_nodes.items() if len(exts) == 1][:10]

    by_type_variance = sorted(
        maybe_nodes.items(),
        key=lambda kv: (-len({e["entity_type"] for e in kv[1]}), kv[0]),
    )
    interesting_types = [name for name, _ in by_type_variance[:5]]

    predicted_synth: List[str] = []
    for name, exts in maybe_nodes.items():
        joined = GRAPH_FIELD_SEP.join(sorted({e["description"] for e in exts}))
        tokens = encode_string_by_tiktoken(joined, model_name=tiktoken_model_name)
        if len(tokens) >= summary_max_tokens:
            predicted_synth.append(name)
            if len(predicted_synth) >= 5:
                break

    seen = set()
    out: List[str] = []
    for src in (high_degree, low_degree, interesting_types, predicted_synth):
        for name in src:
            if name in seen:
                continue
            seen.add(name)
            out.append(name)
            if len(out) >= target:
                return out
    return out


def fmt_timestamp(seconds: float) -> str:
    """Seconds -> H:MM:SS string. Matches videorag_query's CSV format."""
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


class QueryRecorder:
    """Per-query instrumentation collector for retrieval-side analysis dumps.

    Every method is a no-op when output_dir is None or query_id is None, so
    callers can construct one unconditionally and let the recorder decide
    whether to actually write to disk.

    Stage timings are captured via a context manager:

        with rec.stage("path1_entity_match"):
            entity_results = await entities_vdb.query(...)

    The recorder writes per-query files under <output_dir>/queries/<query_id>/.
    """

    def __init__(
        self,
        output_dir: Union[str, Path, None],
        query_id: Optional[str],
    ) -> None:
        self.enabled = output_dir is not None and query_id is not None
        self.output_dir = output_dir
        self.query_id = query_id
        self.subdir = f"queries/{query_id}" if self.enabled else None
        self._timings: Dict[str, float] = {}
        self._total_start: Optional[float] = None

    def start_total(self) -> None:
        """Mark the wall-clock start of the query. Call once before stages."""
        if self.enabled:
            self._total_start = time.time()

    @contextmanager
    def stage(self, name: str):
        """Time the wrapped block and record the elapsed seconds under ``name``."""
        if not self.enabled:
            yield
            return
        start = time.time()
        try:
            yield
        finally:
            self._timings[name] = round(time.time() - start, 3)

    def dump(self, filename: str, data) -> None:
        """Write a JSON or text file to ``queries/<query_id>/<filename>``."""
        if not self.enabled:
            return
        dump_analysis(self.subdir, filename, data, self.output_dir)

    def finalize_timing(self) -> None:
        """Write timing.json with total_seconds and the captured per-stage timings."""
        if not self.enabled:
            return
        total = (
            round(time.time() - self._total_start, 3)
            if self._total_start is not None
            else 0.0
        )
        dump_analysis(
            self.subdir,
            "timing.json",
            {"total_seconds": total, "stages": self._timings},
            self.output_dir,
        )
