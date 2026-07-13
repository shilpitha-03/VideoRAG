# """
# extract.py — turn chunks into subgraphs (one LLM call per chunk).

# Pipeline position: chunk.py -> [extract.py] -> merge.py -> inspect.py

# For each chunk:
#   1. build the prompt (prompts.py)
#   2. call the model (llm.py)
#   3. parse the JSON the model returned
#   4. attach provenance (which chunk + which windows it came from)

# The model is asked for {entities, relations}. Provenance is added by US,
# not the model — extraction is per-chunk, so an entity traces back to the
# chunk's whole window range, and our code owns that mapping (no hallucinated
# window numbers).
# """

# import json
# import re

# from llm import complete
# from prompts import build_extraction_prompt, EXTRACTION_INSTRUCTION, ENTITY_TYPES


# def _parse_json(raw):
#     """
#     Models sometimes wrap JSON in ```json ... ``` fences or add stray text.
#     Strip fences, then parse. Returns the dict, or raises with the raw text
#     so you can see what went wrong.
#     """
#     text = raw.strip()
#     # remove a leading ```json or ``` and a trailing ```
#     text = re.sub(r"^```(?:json)?", "", text).strip()
#     text = re.sub(r"```$", "", text).strip()
#     try:
#         return json.loads(text)
#     except json.JSONDecodeError as e:
#         raise ValueError(f"model did not return valid JSON:\n---\n{raw}\n---") from e


# def extract_chunk(chunk):
#     """
#     One chunk dict -> one subgraph dict.
#     Subgraph carries provenance: chunk_id and the window_idxs it came from.
#     """
#     prompt = build_extraction_prompt(chunk["description"])   # <-- match your chunk text key
#     raw = complete(prompt, system=EXTRACTION_INSTRUCTION)
#     parsed = _parse_json(raw)

#     entities = parsed.get("entities", [])
#     # relations = parsed.get("relations", [])
#     events = parsed.get("events", [])
    
#     # --- attach provenance to every entity and relation (WE do this, not the model) ---
#     for e in entities:
#         e["source_chunks"] = [chunk["chunk_id"]]
#         e["source_windows"] = chunk["window_idx"]
#     # for r in relations:
#     #     r["source_chunks"] = [chunk["chunk_id"]]
#     #     r["source_windows"] = chunk["window_idx"]
#     for ev in events:
#         ev["source_chunks"] = [chunk["chunk_id"]]
#         # validate the model's window_idx against the chunk's real windows:
#         if ev.get("window_idx") not in chunk["window_idxs"]:
#             ev["window_idx"] = chunk["window_idxs"][0]   # clamp hallucinated window to chunk start

#     # return {
#     #     "chunk_id": chunk["chunk_id"],
#     #     "entities": entities,
#     #     "relations": relations,
#     # }
#     return {"chunk_id": chunk["chunk_id"], "entities": entities, "events": events}


# def validate_subgraph(subgraph):
#     """
#     Cheap sanity checks for the single-chunk gate. Returns a list of warnings
#     (empty list = clean). Does NOT raise — you want to SEE the problems.
#     """
#     warnings = []
#     names = {e["name"] for e in subgraph["entities"]}

#     for e in subgraph["entities"]:
#         if e["type"] not in ENTITY_TYPES:
#             warnings.append(f"bad type: {e['name']!r} -> {e['type']!r}")
#         if not e.get("description"):
#             warnings.append(f"empty description: {e['name']!r}")

#     # every relation endpoint should be a declared entity
#     for r in subgraph["relations"]:
#         if r["source"] not in names:
#             warnings.append(f"relation source not in entities: {r['source']!r}")
#         if r["target"] not in names:
#             warnings.append(f"relation target not in entities: {r['target']!r}")

#     for ev in subgraph["events"]:
#         if ev["source"] not in names:
#             warnings.append(f"relation source not in entities: {ev['source']!r}")
#         if ev["target"] not in names:
#             warnings.append(f"relation target not in entities: {ev['target']!r}")

#     return warnings


# def extract_all(chunks):
#     """Run extraction across every chunk. Call this ONLY after the single-chunk gate passes."""
#     subgraphs = []
#     for chunk in chunks:
#         sg = extract_chunk(chunk)
#         # print(f"chunk {sg['chunk_id']}: {len(sg['entities'])} entities, {len(sg['relations'])} relations")
#         print(f"chunk {sg['chunk_id']}: {len(sg['entities'])} entities, {len(sg['events'])} events")
#         subgraphs.append(sg)
#     return subgraphs






# """
# extract.py — turn chunks into subgraphs (one LLM call per chunk).  [RUN 2: events]

# Pipeline position: chunk.py -> [extract.py] -> merge.py -> inspect.py

# For each chunk:
#   1. build the prompt (prompts.py)
#   2. call the model (llm.py)
#   3. parse the JSON the model returned  -> {entities, events}
#   4. attach provenance + validate each event's window_idx against this chunk

# The model emits entities + events (NOT edges). Edges (INVOLVES/ACTS_ON/EXPOSES/
# PRECEDES) are built later in merge.py from the event slots and the timeline.
# """

# import json
# import re

# from llm import complete
# from prompts import build_extraction_prompt, EXTRACTION_INSTRUCTION, ENTITY_TYPES


# def _parse_json(raw):
#     """Strip ```json fences if present, then parse. Raise WITH the raw text on failure."""
#     text = raw.strip()
#     text = re.sub(r"^```(?:json)?", "", text).strip()
#     text = re.sub(r"```$", "", text).strip()
#     try:
#         return json.loads(text)
#     except json.JSONDecodeError as e:
#         raise ValueError(f"model did not return valid JSON:\n---\n{raw}\n---") from e


# def extract_chunk(chunk):
#     """One chunk dict -> one subgraph dict {chunk_id, entities, events}."""
#     prompt = build_extraction_prompt(chunk["description"])
#     raw = complete(prompt, system=EXTRACTION_INSTRUCTION)
#     parsed = _parse_json(raw)

#     # Required keys — no silent default. If the model didn't return these, crash loudly.
#     entities = parsed["entities"]
#     events = parsed["events"]

#     valid_windows = chunk["window_idx"]          # the real windows in THIS chunk

#     # provenance for entities (whole-chunk range, same as baseline)
#     for e in entities:
#         e["source_chunks"] = [chunk["chunk_id"]]
#         e["source_windows"] = valid_windows

#     # provenance for events + validate the model's window_idx against the chunk
#     for ev in events:
#         ev["source_chunks"] = [chunk["chunk_id"]]
#         if ev.get("window_idx") not in valid_windows:
#             ev["window_idx"] = valid_windows[0]   # clamp a hallucinated/missing window

#     return {"chunk_id": chunk["chunk_id"], "entities": entities, "events": events}


# def validate_subgraph(subgraph):
#     """Cheap sanity checks for the single-chunk gate. Returns warnings (empty = clean)."""
#     warnings = []
#     names = {e["name"] for e in subgraph["entities"]}

#     for e in subgraph["entities"]:
#         if e["type"] not in ENTITY_TYPES:
#             warnings.append(f"bad type: {e['name']!r} -> {e['type']!r}")
#         if not e.get("description"):
#             warnings.append(f"empty description: {e['name']!r}")

#     # every entity an event references must be declared in entities
#     for ev in subgraph["events"]:
#         if ev.get("instrument") not in names:
#             warnings.append(f"event instrument not in entities: {ev.get('instrument')!r}")
#         if ev.get("target") not in names:
#             warnings.append(f"event target not in entities: {ev.get('target')!r}")
#         # exposes is optional (can be null); only check when present
#         if ev.get("exposes") is not None and ev["exposes"] not in names:
#             warnings.append(f"event exposes not in entities: {ev['exposes']!r}")

#     return warnings


# def extract_all(chunks):
#     """Run extraction across every chunk. Call ONLY after the single-chunk gate passes."""
#     subgraphs = []
#     for chunk in chunks:
#         sg = extract_chunk(chunk)
#         print(f"chunk {sg['chunk_id']}: {len(sg['entities'])} entities, {len(sg['events'])} events")
#         subgraphs.append(sg)
#     return subgraphs



























































"""
extract.py — turn chunks into subgraphs (one LLM call per chunk).  [RUN 2: events]

Pipeline position: chunk.py -> [extract.py] -> merge.py -> inspect.py

For each chunk:
  1. build the prompt (prompts.py)
  2. call the model (llm.py)
  3. parse the JSON the model returned  -> {entities, events}
  4. attach provenance + validate window_idx + attach the source-window TEXT
     as each event's description (grounded proxy text, NOT model-generated)

The model emits entities (name, type) + events (window_idx, action_type,
instrument, target, exposes). It does NOT emit edges or descriptions.
Edges are built later in merge.py. Event descriptions are the source window text,
attached here in code so the retrievable text stays grounded and never paraphrased.
"""

import json
import re

from llm import complete
from prompts import build_extraction_prompt, EXTRACTION_INSTRUCTION, ENTITY_TYPES


def _parse_json(raw):
    """Strip ```json fences if present, then parse. Raise WITH the raw text on failure."""
    text = raw.strip()
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"model did not return valid JSON:\n---\n{raw}\n---") from e


def extract_chunk(chunk, windows_by_idx):
    """
    One chunk dict -> one subgraph dict {chunk_id, entities, events}.
    windows_by_idx: {window_idx: description} lookup for attaching grounded text.
    """
    prompt = build_extraction_prompt(chunk["description"])
    raw = complete(prompt, system=EXTRACTION_INSTRUCTION)
    parsed = _parse_json(raw)

    # required keys — crash loudly if the model didn't return them
    entities = parsed["entities"]
    events = parsed["events"]

    valid_windows = chunk["window_idxs"]          # PLURAL — matches chunk.py

    # provenance for entities (whole-chunk range)
    for e in entities:
        e["source_chunks"] = [chunk["chunk_id"]]
        e["source_windows"] = valid_windows

    # provenance + window validation + grounded description for events
    for ev in events:
        ev["source_chunks"] = [chunk["chunk_id"]]
        if ev.get("window_idx") not in valid_windows:
            ev["window_idx"] = valid_windows[0]   # clamp hallucinated/missing window
        # attach the source window's own text as the description (grounded, not paraphrased)
        ev["description"] = windows_by_idx.get(ev["window_idx"], "")

    return {"chunk_id": chunk["chunk_id"], "entities": entities, "events": events}


def validate_subgraph(subgraph):
    """Cheap sanity checks for the single-chunk gate. Returns warnings (empty = clean)."""
    warnings = []
    names = {e["name"] for e in subgraph["entities"]}

    for e in subgraph["entities"]:
        if e["type"] not in ENTITY_TYPES:
            warnings.append(f"bad type: {e['name']!r} -> {e['type']!r}")

    for ev in subgraph["events"]:
        instr = ev.get("instrument")
        if instr is not None and instr not in names:
            warnings.append(f"event instrument not in entities: {instr!r}")
        if ev.get("target") not in names:
            warnings.append(f"event target not in entities: {ev.get('target')!r}")
        if ev.get("exposes") is not None and ev["exposes"] not in names:
            warnings.append(f"event exposes not in entities: {ev['exposes']!r}")

    return warnings


def extract_all(chunks, windows_by_idx):
    """Run extraction across every chunk. Call ONLY after the single-chunk gate passes."""
    subgraphs = []
    for chunk in chunks:
        sg = extract_chunk(chunk, windows_by_idx)
        print(f"chunk {sg['chunk_id']}: {len(sg['entities'])} entities, {len(sg['events'])} events")
        subgraphs.append(sg)
    return subgraphs