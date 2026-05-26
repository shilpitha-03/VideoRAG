"""Instrumentation helpers for dumping intermediate pipeline outputs to disk.

All functions in this module are no-ops when output_dir is None — pipeline
behavior must be unchanged whether analysis instrumentation is on or off.
"""

import json
from pathlib import Path
from typing import Union


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
