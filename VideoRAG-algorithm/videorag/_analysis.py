"""Instrumentation helpers for dumping intermediate pipeline outputs to disk.

All functions in this module are no-ops when output_dir is None — pipeline
behavior must be unchanged whether analysis instrumentation is on or off.
"""

import json
from pathlib import Path
from typing import Dict, List, Union


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
