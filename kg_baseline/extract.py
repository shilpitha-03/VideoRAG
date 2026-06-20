"""
extract.py — turn chunks into subgraphs (one LLM call per chunk).

Pipeline position: chunk.py -> [extract.py] -> merge.py -> inspect.py

For each chunk:
  1. build the prompt (prompts.py)
  2. call the model (llm.py)
  3. parse the JSON the model returned
  4. attach provenance (which chunk + which windows it came from)

The model is asked for {entities, relations}. Provenance is added by US,
not the model — extraction is per-chunk, so an entity traces back to the
chunk's whole window range, and our code owns that mapping (no hallucinated
window numbers).
"""

import json
import re

from llm import complete
from prompts import build_extraction_prompt, EXTRACTION_INSTRUCTION, ENTITY_TYPES


def _parse_json(raw):
    """
    Models sometimes wrap JSON in ```json ... ``` fences or add stray text.
    Strip fences, then parse. Returns the dict, or raises with the raw text
    so you can see what went wrong.
    """
    text = raw.strip()
    # remove a leading ```json or ``` and a trailing ```
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"model did not return valid JSON:\n---\n{raw}\n---") from e


def extract_chunk(chunk):
    """
    One chunk dict -> one subgraph dict.
    Subgraph carries provenance: chunk_id and the window_idxs it came from.
    """
    prompt = build_extraction_prompt(chunk["description"])   # <-- match your chunk text key
    raw = complete(prompt, system=EXTRACTION_INSTRUCTION)
    parsed = _parse_json(raw)

    entities = parsed.get("entities", [])
    relations = parsed.get("relations", [])

    # --- attach provenance to every entity and relation (WE do this, not the model) ---
    for e in entities:
        e["source_chunks"] = [chunk["chunk_id"]]
        e["source_windows"] = chunk["window_idxs"]
    for r in relations:
        r["source_chunks"] = [chunk["chunk_id"]]
        r["source_windows"] = chunk["window_idxs"]

    return {
        "chunk_id": chunk["chunk_id"],
        "entities": entities,
        "relations": relations,
    }


def validate_subgraph(subgraph):
    """
    Cheap sanity checks for the single-chunk gate. Returns a list of warnings
    (empty list = clean). Does NOT raise — you want to SEE the problems.
    """
    warnings = []
    names = {e["name"] for e in subgraph["entities"]}

    for e in subgraph["entities"]:
        if e["type"] not in ENTITY_TYPES:
            warnings.append(f"bad type: {e['name']!r} -> {e['type']!r}")
        if not e.get("description"):
            warnings.append(f"empty description: {e['name']!r}")

    # every relation endpoint should be a declared entity
    for r in subgraph["relations"]:
        if r["source"] not in names:
            warnings.append(f"relation source not in entities: {r['source']!r}")
        if r["target"] not in names:
            warnings.append(f"relation target not in entities: {r['target']!r}")

    return warnings


def extract_all(chunks):
    """Run extraction across every chunk. Call this ONLY after the single-chunk gate passes."""
    subgraphs = []
    for chunk in chunks:
        sg = extract_chunk(chunk)
        print(f"chunk {sg['chunk_id']}: {len(sg['entities'])} entities, {len(sg['relations'])} relations")
        subgraphs.append(sg)
    return subgraphs