# """
# merge.py — collapse the 11 per-chunk subgraphs into one global graph.

# Pipeline position: chunk.py -> extract.py -> [merge.py] -> inspect.py

# Two parts:
#   1. MECHANICAL grouping (no LLM): gather entities by normalized name,
#      relations by normalized (source, target) pair.
#   2. LLM SYNTHESIS: when a group has more than one description, fuse them
#      into a single description with one model call.

# Provenance (source_chunks / source_windows) is UNIONED across the group, so a
# merged node remembers every chunk and window it came from.

# NOTE on the Level-3 finding: collapsing all relations between the same pair into
# ONE edge is exactly where event order is lost. Three distinct "sickle knife ->
# uncinate process" moments become a single co-occurrence edge. That collapse is
# VideoRAG's schema behaving as designed — and it's the thing to point at when you
# argue for typed/ordered edges in a later run.
# """

# import json
# from collections import defaultdict

# from llm import complete


# def _norm(name):
#     """Normalize a name for matching: lowercase, trimmed. (Extraction already
#     canonicalizes; this is a defensive second pass so 'Sickle knife ' still merges.)"""
#     return name.strip().lower()


# # ---------------------------------------------------------------------------
# # LLM synthesis: many descriptions of one thing -> a single description.
# # ---------------------------------------------------------------------------
# def _synthesize_entity(name, descriptions):
#     joined = "\n".join(f"- {d}" for d in descriptions)
#     prompt = (
#         f'Entity: "{name}"\n'
#         f"Here are descriptions of this entity collected from different parts of a surgery:\n"
#         f"{joined}\n\n"
#         f"Write ONE concise description (1-2 sentences) that merges these, removing "
#         f"redundancy and resolving overlap. Output only the description text, nothing else."
#     )
#     return complete(prompt).strip()


# def _synthesize_relation(source, target, descriptions):
#     joined = "\n".join(f"- {d}" for d in descriptions)
#     prompt = (
#         f'Relationship: "{source}" -> "{target}"\n'
#         f"Here are descriptions of what happened between them, from different moments:\n"
#         f"{joined}\n\n"
#         f"Write ONE concise description (1-2 sentences) that merges these. Output only "
#         f"the description text, nothing else."
#     )
#     return complete(prompt).strip()


# # ---------------------------------------------------------------------------
# # Part 1: mechanical grouping helpers (no LLM). This is the 'group by key'
# # pattern — worth rewriting from blank for interview practice.
# # ---------------------------------------------------------------------------
# def _group_entities(subgraphs):
#     groups = defaultdict(list)             # normalized name -> list of entity dicts
#     for sg in subgraphs:
#         for e in sg["entities"]:
#             groups[_norm(e["name"])].append(e)
#     return groups


# def _group_relations(subgraphs):
#     groups = defaultdict(list)             # (norm source, norm target) -> list of relation dicts
#     for sg in subgraphs:
#         for r in sg["relations"]:
#             key = (_norm(r["source"]), _norm(r["target"]))
#             groups[key].append(r)
#     return groups


# # ---------------------------------------------------------------------------
# # Merge one group into one node / edge.
# # ---------------------------------------------------------------------------
# def _merge_entity_group(name, group):
#     types = [e["type"] for e in group]
#     merged_type = max(set(types), key=types.count)          # majority vote

#     descriptions = [e["description"] for e in group]
#     if len(descriptions) == 1:
#         description = descriptions[0]
#     else:
#         description = _synthesize_entity(name, descriptions)  # LLM only when needed

#     chunks = sorted({c for e in group for c in e["source_chunks"]})
#     windows = sorted({w for e in group for w in e["source_windows"]})

#     return {
#         "name": name,
#         "type": merged_type,
#         "description": description,
#         "source_chunks": chunks,
#         "source_windows": windows,
#         "mention_count": len(group),       # how many subgraphs contributed (useful for inspection)
#     }


# def _merge_relation_group(source, target, group):
#     descriptions = [r["description"] for r in group]
#     if len(descriptions) == 1:
#         description = descriptions[0]
#     else:
#         description = _synthesize_relation(source, target, descriptions)

#     chunks = sorted({c for r in group for c in r["source_chunks"]})
#     windows = sorted({w for r in group for w in r["source_windows"]})

#     return {
#         "source": source,
#         "target": target,
#         "description": description,
#         "source_chunks": chunks,
#         "source_windows": windows,
#         "mention_count": len(group),
#     }


# # ---------------------------------------------------------------------------
# # Top level.
# # ---------------------------------------------------------------------------
# def merge_subgraphs(subgraphs):
#     ent_groups = _group_entities(subgraphs)
#     rel_groups = _group_relations(subgraphs)

#     merged_nodes = [_merge_entity_group(name, g) for name, g in ent_groups.items()]
#     merged_edges = [_merge_relation_group(src, tgt, g) for (src, tgt), g in rel_groups.items()]

#     return {"entities": merged_nodes, "relations": merged_edges}

# """
# merge.py — build the global graph from per-chunk subgraphs.  [RUN 2: events + typed edges]

# Pipeline position: chunk.py -> extract.py -> [merge.py] -> inspect.py

# Three jobs:
#   1. ENTITIES  — merge by name (same as baseline): group, synthesize, union provenance.
#   2. EVENTS    — do NOT merge. Each event is a distinct moment; keep them all, give IDs.
#   3. EDGES     — build them here, mechanically (no LLM):
#         INVOLVES : event -> instrument   (from event["instrument"])
#         ACTS_ON  : event -> target       (from event["target"])
#         EXPOSES  : event -> exposes       (from event["exposes"], only if not null)
#         PRECEDES : event -> event         (sort all events by window_idx, link consecutive)

# Output graph shape: {"entities": [...], "events": [...], "edges": [...]}
# """

# from collections import defaultdict
# from llm import complete


# def _norm(name):
#     return name.strip().lower()


# # ---------------------------------------------------------------------------
# # ENTITIES — unchanged from baseline.
# # ---------------------------------------------------------------------------
# def _synthesize_entity(name, descriptions):
#     joined = "\n".join(f"- {d}" for d in descriptions)
#     prompt = (
#         f'Entity: "{name}"\n'
#         f"Descriptions collected from different parts of a surgery:\n{joined}\n\n"
#         f"Write ONE concise description (1-2 sentences) merging these. Output only the text."
#     )
#     return complete(prompt).strip()


# def _merge_entity_group(name, group):
#     types = [e["type"] for e in group]
#     descriptions = [e["description"] for e in group]
#     description = descriptions[0] if len(descriptions) == 1 else _synthesize_entity(name, descriptions)
#     return {
#         "name": name,
#         "type": max(set(types), key=types.count),
#         "description": description,
#         "source_chunks": sorted({c for e in group for c in e["source_chunks"]}),
#         "source_windows": sorted({w for e in group for w in e["source_windows"]}),
#         "mention_count": len(group),
#     }


# def _merge_entities(subgraphs):
#     groups = defaultdict(list)
#     for sg in subgraphs:
#         for e in sg["entities"]:
#             groups[_norm(e["name"])].append(e)
#     return [_merge_entity_group(name, g) for name, g in groups.items()]


# # ---------------------------------------------------------------------------
# # EVENTS — collected, never merged. Each gets a stable id.
# # ---------------------------------------------------------------------------
# def _collect_events(subgraphs):
#     events = []
#     counter = 0
#     for sg in subgraphs:
#         for ev in sg["events"]:
#             events.append({
#                 "event_id": f"evt_{counter:03d}",
#                 "window_idx": ev["window_idx"],
#                 "action_type": ev.get("action_type"),
#                 "instrument": _norm(ev["instrument"]),     # normalize so it matches merged entity names
#                 "target": _norm(ev["target"]),
#                 "exposes": _norm(ev["exposes"]) if ev.get("exposes") else None,
#                 "description": ev.get("description", ""),
#                 "source_chunks": ev["source_chunks"],
#             })
#             counter += 1
#     return events


# # ---------------------------------------------------------------------------
# # EDGES — built mechanically from event slots + the timeline.
# # ---------------------------------------------------------------------------
# def _build_edges(events):
#     edges = []

#     # slot edges: one event connects to its instrument, its target, its exposes
#     for ev in events:
#         edges.append({"source": ev["event_id"], "target": ev["instrument"], "type": "INVOLVES"})
#         edges.append({"source": ev["event_id"], "target": ev["target"],     "type": "ACTS_ON"})
#         if ev["exposes"]:
#             edges.append({"source": ev["event_id"], "target": ev["exposes"], "type": "EXPOSES"})

#     # PRECEDES: sort events in time, link each to the next
#     ordered = sorted(events, key=lambda ev: ev["window_idx"])
#     for a, b in zip(ordered, ordered[1:]):
#         edges.append({"source": a["event_id"], "target": b["event_id"], "type": "PRECEDES"})

#     return edges


# # ---------------------------------------------------------------------------
# # Top level.
# # ---------------------------------------------------------------------------
# def merge_subgraphs(subgraphs):
#     entities = _merge_entities(subgraphs)
#     events = _collect_events(subgraphs)
#     edges = _build_edges(events)
#     return {"entities": entities, "events": events, "edges": edges}













"""
merge.py — build the action-level graph from per-chunk subgraphs.
[Entities merged; events kept distinct; INVOLVES/ACTS_ON/EXPOSES edges built.
 No PRECEDES, no triplet merge — those wait for step classification.]

Output: {"entities": [...], "events": [...], "edges": [...]}
"""

from collections import defaultdict


def _norm(name):
    return name.strip().lower() if name else name


# --- ENTITIES: merge by name (instruments + anatomy) ---
def _merge_entities(subgraphs):
    groups = defaultdict(list)
    for sg in subgraphs:
        for e in sg["entities"]:
            groups[_norm(e["name"])].append(e)

    merged = []
    for name, group in groups.items():
        types = [e["type"] for e in group]
        merged.append({
            "name": name,
            "type": max(set(types), key=types.count),      # majority type
            "source_chunks": sorted({c for e in group for c in e["source_chunks"]}),
            "source_windows": sorted({w for e in group for w in e["source_windows"]}),
            "mention_count": len(group),
        })
    return merged


# --- EVENTS: kept distinct, each gets a stable id, names normalized to match merged entities ---
def _collect_events(subgraphs):
    events = []
    counter = 0
    for sg in subgraphs:
        for ev in sg["events"]:
            events.append({
                "event_id": f"evt_{counter:03d}",
                "window_idx": ev["window_idx"],
                "action_type": ev.get("action_type"),
                "instrument": _norm(ev.get("instrument")),   # None stays None
                "target": _norm(ev.get("target")),
                "exposes": _norm(ev.get("exposes")),
                "description": ev.get("description", ""),      # grounded window text
                "source_chunks": ev["source_chunks"],
            })
            counter += 1
    return events


# --- EDGES: built from event slots. INVOLVES, ACTS_ON, EXPOSES. No PRECEDES yet. ---
def _build_edges(events):
    edges = []
    for ev in events:
        if ev["instrument"]:
            edges.append({"source": ev["event_id"], "target": ev["instrument"], "type": "INVOLVES"})
        if ev["target"]:
            edges.append({"source": ev["event_id"], "target": ev["target"], "type": "ACTS_ON"})
        if ev["exposes"]:
            edges.append({"source": ev["event_id"], "target": ev["exposes"], "type": "EXPOSES"})
    return edges


def merge_subgraphs(subgraphs):
    entities = _merge_entities(subgraphs)
    events = _collect_events(subgraphs)
    edges = _build_edges(events)
    return {"entities": entities, "events": events, "edges": edges}