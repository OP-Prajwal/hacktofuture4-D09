"""
Phase 3 — Query Engine

Provides natural language querying over the codebase graph.
User question → Graph search (tag-based) → Context extraction → LLM reasoning → Answer.
"""

import requests
import json
from db.neo4j_db import neo4j_db
from .semantic_enricher import TAG_RULES

# ── LLM Integration (Phase 3) ────────────────────────────────────────────────
# Configured for qwen2.5-coder:3b
LLM_API_URL = "http://localhost:11434/api/generate"
USE_LLM = True  # Set to True when Ollama server is running

def _get_repo_stats(project_path: str) -> str:
    """Fetch global node counts for the project to provide perspective to the AI."""
    q = "MATCH (n {project: $p}) RETURN labels(n)[0] as type, count(*) as count"
    try:
        print(f"[CIG Stats] Fetching counts for: {project_path}")
        results = neo4j_db.run_query(q, {"p": project_path})
        print(f"[CIG Stats] Raw Results: {results}")
        if not results:
            return "None (empty graph)"
        
        stats = []
        for r in results:
            label = r.get("type") or "Unknown"
            count = r.get("count", 0)
            # Pluralize correctly
            p_label = f"{label}es" if label.endswith('s') or label.endswith('ch') or label.endswith('sh') else f"{label}s"
            stats.append(f"{p_label}: {count}")
        return ", ".join(stats)
    except Exception as e:
        print(f"[CIG Stats] Failed: {e}")
        return "Unknown (database error)"

def ask_repository(workspace: str, project_name: str, question: str) -> dict:
    """
    Query flow:
    1. Extract keywords from question to find relevant tags
    2. Query Neo4j for nodes with those tags
    3. Expand neighbors (calls/dependencies)
    4. Pass context to LLM for final answer
    """
    project_path = f"{workspace}/{project_name}"
    
    # 1. Identify relevant tags
    q_lower = question.lower()
    relevant_tags = []
    for keywords, tag in TAG_RULES:
        if any(kw in q_lower for kw in keywords):
            if tag not in relevant_tags:
                relevant_tags.append(tag)
                
    # 2. Search graph for these tags
    if not relevant_tags:
        # ── Fallback: Repo Overview ──
        # If no specific tags match, fetch the most important/connected nodes.
        # Use coalesce to handle cases where blast_radius might be missing on old nodes.
        query = """
        MATCH (n {project: $project_path})
        RETURN n, labels(n) as labels
        ORDER BY coalesce(n.blast_radius, 0) DESC
        LIMIT 10
        """
        params = {"project_path": project_path}
    else:
        query = """
        MATCH (n {project: $project_path})
        WHERE any(t IN n.tags WHERE t IN $tags) OR labels(n)[0] IN $labels
        RETURN n, labels(n) as labels 
        ORDER BY coalesce(n.blast_radius, 0) DESC
        LIMIT 20
        """
        params = {
            "project_path": project_path, 
            "tags": relevant_tags,
            "labels": [t for t in relevant_tags if t in {"Function", "Class", "File", "Module"}]
        }
    
    try:
        print("query ",query)
        print("params ",params)
        results = neo4j_db.run_query(query, params)
        print("neo4j results ",results)
    except Exception as e:
        print(f"[CIG Query] Graph offline ({e}), returning empty.")
        results = []
        
    context_nodes = []
    node_ids = []
    for record in results:
        node = record["n"]
        label = record["labels"][0] if record["labels"] else "Unknown"
        qname = node.get("qualified_name") or node.get("name")
        node_ids.append(qname)
        
        context_nodes.append({
            "type": label,
            "name": qname,
            "summary": node.get("summary", ""),
            "tags": node.get("tags", []),
            "file": node.get("file_path", "")
        })
        
    # 3. Deep Traversal (Path Tracing)
    # We don't just want neighbors; we want to see the "flow"
    trace_map = []
    if node_ids and results:
        # Find paths up to 2 hops away to trace the logic flow
        path_query = """
        MATCH p = (a)-[r:CALLS|IMPORTS|EXTENDS*1..2]->(b)
        WHERE (a.project = $path) 
          AND (a.qualified_name IN $nodes)
          AND (a <> b)
        RETURN 
            [n in nodes(p) | n.qualified_name] as path_nodes,
            [rel in relationships(p) | type(rel)] as rel_types
        LIMIT 15
        """
        try:
            paths = neo4j_db.run_query(path_query, {"path": project_path, "nodes": node_ids})
            for entry in paths:
                steps = []
                p_nodes = entry['path_nodes']
                p_rels = entry['rel_types']
                for i in range(len(p_rels)):
                    steps.append(f"{p_nodes[i]} --[{p_rels[i]}]--> {p_nodes[i+1]}")
                trace_map.append(" -> ".join(steps))
        except Exception as e:
            print(f"[CIG Query] Traversal failed: {e}")

    # 4. Include Global Stats
    repo_stats = _get_repo_stats(project_path)
    print(f"[CIG Query] Final Repo Stats: {repo_stats}")

    # Build context prompt with structural hierarchy
    context_str = f"### Overall Repository Statistics\n{repo_stats}\n\n"
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
        for trace in list(set(trace_map))[:10]: # De-duplicate and limit
            context_str += f"- {trace}\n"
        context_str += "\n"

    # 5. Ask LLM
    answer = ""
    # Instruct the LLM to think like an architect using the graph paths
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
        "1. Locate relevant nodes/functions in the graph.\n"
        "2. Traverse their connections.\n"
        "3. Understand the flow and relationships.\n"
        "4. Use both specific traversed nodes AND the 'Overall Repository Statistics' to formulate your answer.\n"
        "5. Answer based ONLY on this understanding.\n\n"
        "Strict Rules\n"
        "- Do NOT hallucinate anything outside the graph.\n"
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
        # Mock LLM response if offline
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
