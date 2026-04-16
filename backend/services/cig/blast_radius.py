"""
Blast Radius Calculator

Queries the Neo4j code intelligence graph to determine the impact
of changed files. Returns affected symbols, files, and test skip
recommendations for CI acceleration.
"""

from __future__ import annotations

from db.mongo import mongo

def calculate_blast_radius(project_path: str, changed_files: list[str]) -> dict:
    """
    Given a list of changed file paths, dynamically reconstruct the graph
    from MongoDB arrays and use BFS to find:
    - All symbols (functions/classes) in those files
    - All upstream dependents (d=1, d=2)
    - Which files are safe to skip testing on
    """
    if not changed_files:
        return {
            "changed_files": [],
            "affected_symbols": [],
            "affected_files": [],
            "unaffected_files": [],
            "risk_level": "NONE",
            "recommendation": "No files changed."
        }

    doc = mongo.get_collection("graphs").find_one({"project": project_path}, {"_id": 0})
    if not doc:
        return {
            "changed_files": changed_files,
            "affected_symbols": [],
            "affected_files": changed_files,
            "unaffected_files": [],
            "risk_level": "UNKNOWN",
            "recommendation": "Could not find graph data. Run 'Create Knowledge Graph' first."
        }

    nodes = doc.get("nodes", [])
    edges = doc.get("edges", [])

    # 1. Find all symbols in the changed files and map files
    changed_nodes = []
    all_files = set()
    node_by_id = {}

    for n in nodes:
         node_id = n.get("id") or n.get("qualified_name")
         if not node_id: continue
         node_by_id[node_id] = n

         fpath = n.get("file") or n.get("file_path") or n.get("data", {}).get("file", "")
         if fpath:
             all_files.add(fpath)

         n_name = n.get("name") or n.get("data", {}).get("label", "")
         for cf in changed_files:
             if (fpath and fpath.endswith(cf)) or (n_name and n_name.endswith(cf)):
                 changed_nodes.append(n)
                 break

    if not changed_nodes:
        return {
            "changed_files": changed_files,
            "affected_symbols": [],
            "affected_files": changed_files,
            "unaffected_files": [],
            "risk_level": "UNKNOWN",
            "recommendation": "Could not find changed files in the graph."
        }

    changed_node_ids = {n.get("id") for n in changed_nodes}
    changed_symbol_names = [n.get("name") or n.get("id", "").split("/")[-1] for n in changed_nodes]

    # 2. Build in-memory undirected graph for blast radius traversal
    adj = {}
    valid_rels = {'CALLS', 'IMPORTS', 'DEPENDS_ON', 'EXTENDS'}
    for e in edges:
        t = e.get("type", "")
        if t not in valid_rels:
            continue
        src = e.get("source")
        tgt = e.get("target")
        if src and tgt:
            if src not in adj: adj[src] = []
            if tgt not in adj: adj[tgt] = []
            if tgt not in adj[src]: adj[src].append(tgt)
            if src not in adj[tgt]: adj[tgt].append(src)

    # 3. Traversal (BFS)
    d1_nodes_dict = {}
    d2_nodes_dict = {}

    for cid in changed_node_ids:
        neighbors_d1 = adj.get(cid, [])
        for n1_id in neighbors_d1:
            if n1_id in changed_node_ids: continue
            
            node1 = node_by_id.get(n1_id)
            if node1 and n1_id not in d1_nodes_dict:
                d1_nodes_dict[n1_id] = node1
            
            # Step out to d=2
            neighbors_d2 = adj.get(n1_id, [])
            for n2_id in neighbors_d2:
                if n2_id in changed_node_ids or n2_id == cid: continue
                node2 = node_by_id.get(n2_id)
                if node2 and n2_id not in d1_nodes_dict and n2_id not in d2_nodes_dict:
                    d2_nodes_dict[n2_id] = node2

    d1_nodes = list(d1_nodes_dict.values())
    d2_nodes = list(d2_nodes_dict.values())

    # 5. Build the affected set
    affected_files = set(changed_files)
    affected_symbols = list(changed_symbol_names)

    d1_details = []
    for n in d1_nodes:
        fpath = n.get("file") or n.get("file_path") or ""
        name = n.get("name") or n.get("id", "").split("/")[-1]
        ntype = n.get("type") or "Unknown"

        if fpath:
            affected_files.add(fpath)
        if name and name not in affected_symbols:
            affected_symbols.append(name)
            
        d1_details.append({
            "name": name,
            "file": fpath,
            "type": ntype,
            "depth": 1,
            "risk": "WILL_BREAK"
        })

    d2_details = []
    for n in d2_nodes:
        fpath = n.get("file") or n.get("file_path") or ""
        name = n.get("name") or n.get("id", "").split("/")[-1]
        ntype = n.get("type") or "Unknown"

        if fpath:
            affected_files.add(fpath)
            
        d2_details.append({
            "name": name,
            "file": fpath,
            "type": ntype,
            "depth": 2,
            "risk": "LIKELY_AFFECTED"
        })

    # 6. Determine unaffected files (safe to skip)
    unaffected_files = sorted(all_files - affected_files)

    # 7. Risk level (Calculate dynamic max blast)
    max_blast = max((n.get("blast_radius") or len(adj.get(n.get("id"), [])) for n in changed_nodes), default=0)
    
    if max_blast >= 8 or len(d1_nodes) >= 5:
        risk_level = "CRITICAL"
        recommendation = "Run FULL test suite. High blast radius detected."
    elif max_blast >= 4 or len(d1_nodes) >= 3:
        risk_level = "HIGH"
        recommendation = f"Run tests for: {', '.join(sorted(affected_files))}. Skip: {', '.join(unaffected_files[:5])}."
    elif len(d1_nodes) >= 1:
        risk_level = "MEDIUM"
        recommendation = f"Run targeted tests only. {len(unaffected_files)} file(s) can be safely skipped."
    else:
        risk_level = "LOW"
        recommendation = f"Isolated change. Only test {', '.join(changed_files)}."

    return {
        "changed_files": changed_files,
        "affected_symbols": affected_symbols,
        "affected_files": sorted(affected_files),
        "unaffected_files": unaffected_files,
        "d1_direct": d1_details,
        "d2_indirect": d2_details,
        "risk_level": risk_level,
        "max_blast_radius": max_blast,
        "recommendation": recommendation
    }
