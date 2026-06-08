# graphml_to_kg_json.py — run once per graph to make the JSON your viz script wants
import networkx as nx, json, sys

graphml_path = sys.argv[1]          # e.g. runs/002/workdir/graph_chunk_entity_relation.graphml
out_path     = sys.argv[2]          # e.g. kg_002.json

G = nx.read_graphml(graphml_path)
data = {"entities": {}, "relationships": []}

for n, d in G.nodes(data=True):
    data["entities"][n] = {"entity_type": d.get("entity_type", "UNKNOWN")}

for u, v, d in G.edges(data=True):
    data["relationships"].append({
        "source": u,
        "target": v,
        "weight": float(d.get("weight", 1.0)) if d.get("weight") else 1.0,
        "description": d.get("description", "")
    })

json.dump(data, open(out_path, "w"), indent=2)
print(f"wrote {len(data['entities'])} entities, {len(data['relationships'])} relationships → {out_path}")


#C:\Users\Shilpitha\Desktop\SETIENT\runs-20260601T135220Z-3-001\runs\001\workdir\graph_chunk_entity_relation.graphml.xml
# C:\Users\Shilpitha\Desktop\SETIENT\runs-20260601T135220Z-3-001\runs\003\workdir
