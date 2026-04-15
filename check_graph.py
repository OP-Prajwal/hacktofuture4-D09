from db.mongo import mongo
import json

def check():
    graphs = mongo.get_collection("graphs")
    # Find the most recent graph
    latest = graphs.find_one({}, sort=[("_id", -1)])
    if not latest:
        print("No graphs found")
        return

    print(f"Project: {latest.get('project')}")
    print(f"Total Nodes: {len(latest.get('nodes', []))}")
    
    # Check for gitnexus in node names or files
    gitnexus_nodes = [
        n for n in latest.get('nodes', [])
        if "gitnexus" in n.get('name', '').lower() or "gitnexus" in n.get('file', '').lower()
    ]
    
    print(f"GitNexus-related nodes: {len(gitnexus_nodes)}")
    for n in gitnexus_nodes[:10]:
        print(f"  - {n.get('name')} ({n.get('file')})")

    # Dump full graph to a file for analysis if it's not too huge
    with open("graph_dump.json", "w") as f:
        # Remove source code to keep it small
        for n in latest.get('nodes', []):
            if 'source' in n: del n['source']
        json.dump(latest, f, indent=2, default=str)

if __name__ == "__main__":
    check()
