"""
Phase 3 — Query Engine

Provides natural language querying over the codebase graph.
User question → Graph search (tag-based) → Context extraction → LLM reasoning → Answer.
"""

import requests
import json
import os
from collections import deque
from db.mongo import mongo
from .semantic_enricher import TAG_RULES

# ── LLM Integration (Phase 3) ────────────────────────────────────────────────
# Configured for qwen2.5-coder:3b
LLM_API_URL = "http://localhost:11434/api/generate"
USE_LLM = True  # Set to True when Ollama server is running

def _get_repo_stats(nodes: list[dict]) -> str:
    """Compute global node counts for the project to provide perspective to the AI."""
    if not nodes:
        return "None (empty graph)"
    
    counts_by_type = {}
    for n in nodes:
        ntype = n.get("type", "Unknown")
        counts_by_type[ntype] = counts_by_type.get(ntype, 0) + 1
        
    stats = []
    for label, count in sorted(counts_by_type.items(), key=lambda x: str(x[0])):
        p_label = f"{label}es" if str(label).endswith('s') or str(label).endswith('ch') or str(label).endswith('sh') else f"{label}s"
        stats.append(f"{p_label}: {count}")
    return ", ".join(stats)

def ask_repository(workspace: str, project_name: str, question: str) -> dict:
    """
    Query flow:
    1. Extract keywords from question to find relevant tags
    2. Search flat MongoDB nodes for those tags
    3. Expand neighbors (calls/dependencies) in-memory
    4. Pass context to LLM for final answer
    """
    project_path = f"{workspace}/{project_name}"
    
    # ── FORCE LOAD README ──
    readme_content = ""
    paths_to_check = [
        os.path.join("c:\\nexus-X", project_name, "README.md"),
        os.path.join(project_name, "README.md"),
        os.path.join(project_path, "README.md")
    ]
    for p in paths_to_check:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    readme_content = f.read()
                break
            except Exception:
                pass
                
    # Load graph from Mongo
    doc = mongo.get_collection("graphs").find_one({"project": project_path}, {"_id": 0})
    if not doc:
        return {
            "question": question,
            "answer": "Graph not found. Please click 'Create Knowledge Graph' first.",
            "graph_context": {"nodes_found": 0, "relevant_tags": [], "nodes": []}
        }
        
    all_nodes = doc.get("nodes", [])
    all_edges = doc.get("edges", [])
    
    # 1. Identify relevant tags
    q_lower = question.lower()
    relevant_tags = []
    for keywords, tag in TAG_RULES:
        if any(kw in q_lower for kw in keywords):
            if tag not in relevant_tags:
                relevant_tags.append(tag)
                
    # 2. Search graph for these tags
    matched_nodes = []
    if not relevant_tags:
        # Fallback: Repo Overview (Top 10 highest blast radius)
        sorted_nodes = sorted(all_nodes, key=lambda x: x.get("blast_radius", 0), reverse=True)
        matched_nodes = sorted_nodes[:10]
    else:
        # Filter nodes that have relevant tags OR whose label matches
        relevant_labels = {t for t in relevant_tags if t in {"Function", "Class", "File", "Module"}}
        
        for n in all_nodes:
            n_tags = n.get("tags", [])
            n_type = n.get("type", "")
            
            if any(t in relevant_tags for t in n_tags) or n_type in relevant_labels:
                matched_nodes.append(n)
                
        # Sort by impact and limit
        matched_nodes = sorted(matched_nodes, key=lambda x: x.get("blast_radius", 0), reverse=True)[:20]
        
    context_nodes = []
    node_ids = set()
    node_by_id = {n.get("id") or n.get("qualified_name"): n for n in all_nodes}
    
    for n in matched_nodes:
        nid = n.get("id") or n.get("qualified_name")
        if not nid: continue
        node_ids.add(nid)
        context_nodes.append({
            "type": n.get("type", "Unknown"),
            "name": n.get("name") or nid.split("/")[-1],
            "summary": n.get("summary", ""),
            "tags": n.get("tags", []),
            "file": n.get("file_path") or n.get("file", "")
        })
        
    # 3. Deep Traversal (Path Tracing up to depth 2)
    trace_map = []
    if node_ids and all_edges:
        # Build directed adjacency list
        adj = {}
        valid_rels = {'CALLS', 'IMPORTS', 'EXTENDS'}
        for e in all_edges:
            rel_type = e.get("type", "")
            if rel_type not in valid_rels:
                continue
            src = e.get("source")
            tgt = e.get("target")
            if src and tgt:
                if src not in adj: adj[src] = []
                # Only add if we haven't added this exact edge
                if (tgt, rel_type) not in adj[src]:
                    adj[src].append((tgt, rel_type))
                    
        # BFS up to 2 hops for each starting node
        for start_id in node_ids:
            queue = deque([(start_id, [start_id], [])])  # (current_node, path_nodes, path_rels)
            
            while queue:
                curr, p_nodes, p_rels = queue.popleft()
                
                if len(p_nodes) > 1:
                    # Format standard path: A --[CALLS]--> B
                    steps = []
                    for i in range(len(p_rels)):
                        steps.append(f"{p_nodes[i]} --[{p_rels[i]}]--> {p_nodes[i+1]}")
                    trace_string = " -> ".join(steps)
                    if trace_string not in trace_map:
                        trace_map.append(trace_string)
                
                if len(p_nodes) <= 2:  # Allow 1 more hop (max 2 edges / 3 nodes)
                    for nxt, r_type in adj.get(curr, []):
                        if nxt not in p_nodes:  # Avoid loops
                            queue.append((nxt, p_nodes + [nxt], p_rels + [r_type]))
                            
        # Limit total traced paths to prevent blowing context window
        trace_map = list(set(trace_map))[:15]

    # 4. Include Global Stats
    repo_stats = _get_repo_stats(all_nodes)
    print(f"[CIG Query] Final Repo Stats: {repo_stats}")

    # Build context prompt with structural hierarchy
    context_str = f"### Overall Repository Statistics\n{repo_stats}\n\n"
    
    if readme_content:
        context_str += f"### Repository README.md Content\n[ABSOLUTE GROUND TRUTH - READ CAREFULLY]\n{readme_content}\n\n"
    else:
        # Extract readme dynamically if possible
        for n in all_nodes:
            name = str(n.get("name", ""))
            if name.endswith("README.md"):
                smry = n.get("summary", "")
                if smry:
                    context_str += f"### Repository README.md Content\n{smry}\n\n"
                break

    context_str += "### Codebase Architectural Map\n\n"
    context_str += "#### Core Components:\n"
    if not context_nodes:
        context_str += "- (No specific components matched the search keywords)\n"
    for cn in context_nodes:
        context_str += f"- {cn['name']} ({cn['type']})\n"
        context_str += f"  Summary: {cn['summary']}\n"
        if cn['tags']:
            context_str += f"  Roles: {', '.join(cn['tags'])}\n"
        context_str += "\n"
        
    if trace_map:
        context_str += "#### Logic Flow & Dependencies:\n"
        for trace in trace_map:
            context_str += f"- {trace}\n"
        context_str += "\n"

    # 5. Ask LLM
    answer = ""
    system_instruction = (
        "You are an AI assistant connected to a knowledge graph of the current repository.\n"
        "The graph is already created from the repository. It contains functions, files, modules, "
        "and their relationships (calls, imports, flow). You already have access to all repository context "
        "via this graph.\n\n"
        "Core Responsibility\n"
        "Your job is to understand the repository by traversing the graph:\n"
        "- Move across nodes (especially functions) and their edges.\n"
        "- Analyze: Function logic, Call relationships, Dependencies, Execution flow.\n"
        "- Use the 'Overall Repository Statistics' to understand the total scale of the project.\n"
        "- Build a complete internal understanding of how the repository works.\n\n"
        "Context Handling\n"
        "- Always maintain full awareness of the repository structure.\n"
        "- Use the graph as your single source of truth.\n"
        "- When needed: Traverse connected nodes, Follow call chains, Explore related functions.\n\n"
        "When Answering Questions\n"
        "For every user query:\n"
        "1. ALWAYS check the 'Repository README.md Content' first if provided to understand the project structure and intent properly.\n"
        "2. Locate relevant nodes/functions in the graph.\n"
        "3. Traverse their connections.\n"
        "4. Understand the flow and relationships.\n"
        "5. Use the README, specific traversed nodes AND the 'Overall Repository Statistics' to formulate your answer.\n"
        "6. Answer based ONLY on this understanding.\n\n"
        "Strict Rules\n"
        "- Do NOT hallucinate anything outside the graph.\n"
        "- Do NOT invent fake functions (e.g., proc_0) to fill in gaps.\n"
        "- Do NOT give generic or theoretical answers.\n"
        "- Do NOT assume missing logic — if not present, say so.\n"
        "- Do NOT explain how you retrieved the data.\n"
        "- Always stay grounded in actual graph structure + repo logic.\n\n"
        "Goal\n"
        "Act as a repository-aware AI debugger and explainer that:\n"
        "- Knows how everything is connected.\n"
        "- Understands function-level behavior deeply.\n"
        "- Gives accurate, context-driven answers.\n"
        "- Resolves doubts strictly based on the repository."
    )
    
    prompt = f"{system_instruction}\n\nUser Question: {question}\n\n{context_str}\n\nFinal Answer:"
    
    if USE_LLM:
        try:
            response = requests.post(LLM_API_URL, json={
                "model": "qwen2.5-coder:3b",
                "prompt": prompt,
                "stream": False
            }, timeout=30.0)
            answer = response.json().get("response", "").strip()
        except Exception as e:
            answer = f"Error reaching local LLM: {e}"
    else:
        if not context_nodes:
            answer = "I couldn't find relevant code related to your question in the graph."
        else:
            names = [n["name"] for n in context_nodes[:3]]
            answer = f"[Mock qwen2.5-coder:3b Response]\nBased on the graph, I see relevance in these components: {', '.join(names)}. " \
                     f"They match tags like {', '.join(relevant_tags)}."

    return {
        "question": question,
        "answer": answer,
        "graph_context": {
            "nodes_found": len(context_nodes),
            "relevant_tags": relevant_tags,
            "nodes": context_nodes,
        }
    }
