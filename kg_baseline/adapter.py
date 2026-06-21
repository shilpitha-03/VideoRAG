"""
adapter.py — convert our graph format into the shape visualize_kg.py expects.

Our format            ->  visualizer format
-------------------------  ----------------------------------------
entities: [ {name,type,  ]  entities: { name: {entity_type: TYPE} }
relations: [ {source,...} ] relationships: [ {source,target,weight,description} ]
type: "anatomy"             entity_type: "ANATOMY"   (uppercase for the CSS selectors)
mention_count: 11           weight: 11               (edge thickness = salience)

Two entry points:
  adapt_merged(merged)        -> the consolidated graph
  adapt_subgraphs(subgraphs)  -> the pre-merge graph, node IDs namespaced by chunk
                                 so the same entity in different chunks stays SEPARATE
                                 (that repetition is the fragmentation we want to see)
"""


# def adapt_merged(merged):
#     entities = {}
#     for e in merged["entities"]:
#         entities[e["name"]] = {"entity_type": e["type"].upper()}

#     relationships = []
#     for r in merged["relations"]:
#         relationships.append({
#             "source": r["source"],
#             "target": r["target"],
#             "weight": r.get("mention_count", 1),
#             "description": r["description"],
#         })

#     return {"entities": entities, "relationships": relationships}

def adapt_merged(merged):
    entities = {}
    for e in merged["entities"]:
        entities[e["name"]] = {"entity_type": e["type"].upper()}

    relationships = []
    for r in merged["relations"]:
        if r["source"] in entities and r["target"] in entities:   # both endpoints must be real nodes
            relationships.append({
                "source": r["source"],
                "target": r["target"],
                "weight": r.get("mention_count", 1),
                "description": r["description"],
            })
    return {"entities": entities, "relationships": relationships}


# def adapt_subgraphs(subgraphs):
#     entities = {}
#     relationships = []
#     for sg in subgraphs:
#         c = sg["chunk_id"]
#         for e in sg["entities"]:
#             node_id = f"{e['name']} (c{c})"          # namespace: keeps per-chunk copies distinct
#             entities[node_id] = {"entity_type": e["type"].upper()}
#         for r in sg["relations"]:
#             relationships.append({
#                 "source": f"{r['source']} (c{c})",
#                 "target": f"{r['target']} (c{c})",
#                 "weight": 1,
#                 "description": r["description"],
#             })

#     return {"entities": entities, "relationships": relationships}

def adapt_subgraphs(subgraphs):
    entities = {}
    relationships = []
    for sg in subgraphs:
        c = sg["chunk_id"]
        for e in sg["entities"]:
            entities[f"{e['name']} (c{c})"] = {"entity_type": e["type"].upper()}
        for r in sg["relations"]:
            src, tgt = f"{r['source']} (c{c})", f"{r['target']} (c{c})"
            if src in entities and tgt in entities:
                relationships.append({"source": src, "target": tgt, "weight": 1,
                                      "description": r["description"]})
    return {"entities": entities, "relationships": relationships}