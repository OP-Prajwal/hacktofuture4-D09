import json
d = json.load(open('graph_dump.json', encoding="utf-8-sig"))
print(f"Nodes: {d.get('total_nodes')}")
print(f"Edges: {d.get('total_edges')}")
node_types = {}
for n in d.get("nodes", []):
    node_types[n["label"]] = node_types.get(n["label"], 0) + 1
edge_types = {}
for e in d.get("edges", []):
    edge_types[e["type"]] = edge_types.get(e["type"], 0) + 1
print("Node Types:", node_types)
print("Edge Types:", edge_types)
