from db.mongo import mongo

GRAPH_NODE_LABELS = {"Function", "Class", "File", "Module"}
GRAPH_RELATIONSHIP_TYPES = {"CALLS", "IMPORTS", "EXTENDS", "CONTAINS", "BELONGS_TO", "DEPENDS_ON"}

def locate_incident_nodes(project_path: str, search_terms: list, file_hints: list, symbol_hints: list) -> list:
    """
    Simulates the old Neo4j fault localization query natively in Python using MongoDB flat arrays.
    """
    doc = mongo.get_collection("graphs").find_one({"project": project_path}, {"_id": 0})
    if not doc:
        return []

    nodes = doc.get("nodes", [])
    edges = doc.get("edges", [])

    # Prepare search matching sets
    norm_search_terms = [t.lower() for t in search_terms]
    norm_file_hints = [f.lower() for f in file_hints]
    norm_symbol_hints = set(symbol_hints)

    matched_nodes = []
    
    # Pre-calculate adjacency for outbound edges
    # We only care about target outbound edges (source -> downstream target)
    outbound_adj = {}
    for e in edges:
        t = e.get("type", "")
        if t not in GRAPH_RELATIONSHIP_TYPES:
            continue
        src = e.get("source")
        tgt_id = e.get("target", "")
        if src and tgt_id:
            if src not in outbound_adj:
                outbound_adj[src] = []
            outbound_adj[src].append((tgt_id, t))

    # Node fast lookup for resolving downstream names
    node_name_lookup = {}
    for n in nodes:
        nid = n.get("id") or n.get("qualified_name")
        if nid:
            node_name_lookup[nid] = n.get("name") or n.get("file_path") or nid.split("/")[-1]

    # Find matching nodes
    for n in nodes:
        n_type = n.get("type") or n.get("label") or "Unknown"
        if n_type not in GRAPH_NODE_LABELS:
            continue
            
        n_name = n.get("name") or ""
        q_name = n.get("qualified_name") or n.get("id") or ""
        f_path = n.get("file_path") or n.get("file") or ""
        summary = n.get("summary") or ""
        
        is_match = False
        
        # 1. Exact symbol match
        if n_name in norm_symbol_hints:
            is_match = True
        # 2. File match
        elif any(f_path.endswith(hint) for hint in file_hints):
            is_match = True
        elif f_path in norm_file_hints:
            is_match = True
        # 3. Contains search term
        else:
            q_name_low = q_name.lower()
            f_path_low = f_path.lower()
            sum_low = summary.lower()
            
            for term in norm_search_terms:
                if term in q_name_low or term in f_path_low or term in sum_low:
                    is_match = True
                    break
        
        if is_match:
            # Build outbound
            outbound = []
            if q_name in outbound_adj:
                for tgt_id, rel_type in outbound_adj[q_name][:8]:
                    outbound.append({
                        "rel_type": rel_type,
                        "neighbor": node_name_lookup.get(tgt_id, tgt_id.split("/")[-1])
                    })
            
            matched_nodes.append({
                "labels": [n_type],
                "name": n_name,
                "qualified_name": q_name,
                "file_path": f_path,
                "start_line": n.get("line") or n.get("start_line") or 0,
                "summary": summary,
                "blast_radius": n.get("blast_radius", 0),
                "outbound": outbound
            })

    # Sort and limit
    matched_nodes.sort(key=lambda x: (x["blast_radius"] or 0), reverse=True)
    return matched_nodes[:12]
