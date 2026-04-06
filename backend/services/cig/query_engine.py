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
# Configured for deepseek-v3.1 as per requirements
LLM_API_URL = "http://localhost:11434/api/generate"  # Mocking local DeepSeek
USE_LLM = False  # Set to True when DeepSeek server is running

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
                
    # If no tags matched natively, we would ask LLM to generate a Cypher query.
    # For now, default to searching functions if empty.
    if not relevant_tags:
        relevant_tags = ["API", "Utility", "Machine Learning", "Database"]
        
    # 2. Search graph for these tags
    # Uses MATCH (n) WHERE any(tag IN n.tags WHERE tag IN $tags) 
    query = """
    MATCH (n {project: $path})
    WHERE any(t IN n.tags WHERE t IN $tags)
    RETURN n, labels(n) as labels LIMIT 15
    """
    
    try:
        results = neo4j_db.run_query(query, {"path": project_path, "tags": relevant_tags})
    except Exception as e:
        print(f"[CIG Query] Graph offline ({e}), returning mock topology.")
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
        
    # 3. Expand neighbors (Call graph relationships)
    expanded_edges = []
    if node_ids and results:
        neighbor_query = """
        MATCH (a)-[r:CALLS|IMPORTS|EXTENDS]->(b)
        WHERE (a.project = $path) AND (a.qualified_name IN $nodes OR b.qualified_name IN $nodes)
        RETURN a.qualified_name as caller, type(r) as rel, b.qualified_name as callee LIMIT 20
        """
        try:
            edges = neo4j_db.run_query(neighbor_query, {"path": project_path, "nodes": node_ids})
            for edge in edges:
                expanded_edges.append(f"{edge['caller']} -> {edge['rel']} -> {edge['callee']}")
        except Exception:
            pass

    # Build context prompt
    context_str = "Codebase Context extracted from graph:\n\n"
    for cn in context_nodes:
        context_str += f"- [{cn['type']}] {cn['name']} (File: {cn['file']})\n"
        context_str += f"  Summary: {cn['summary']}\n"
        context_str += f"  Tags: {', '.join(cn['tags'])}\n\n"
        
    if expanded_edges:
        context_str += "Relationships:\n" + "\n".join(f"- {e}" for e in expanded_edges) + "\n\n"

    # 4. Ask LLM
    answer = ""
    prompt = f"User Question: {question}\n\n{context_str}\n\nAnswer the user's question based strictly on the codebase context provided above."
    
    if USE_LLM:
        try:
            response = requests.post(LLM_API_URL, json={
                "model": "deepseek-v3.1",
                "prompt": prompt,
                "stream": False
            }, timeout=30.0)
            answer = response.json().get("response", "").strip()
        except Exception as e:
            answer = f"Error reaching DeepSeek LLM: {e}"
    else:
        # Mock LLM response if offline
        if not context_nodes:
            answer = "I couldn't find relevant code related to your question in the graph."
        else:
            names = [n["name"] for n in context_nodes[:3]]
            answer = f"[Mock DeepSeek-v3.1 Response]\nBased on the graph, I see relevance in these components: {', '.join(names)}. " \
                     f"They match tags like {', '.join(relevant_tags)}."

    return {
        "question": question,
        "answer": answer,
        "graph_context": {
            "nodes_found": len(context_nodes),
            "edges_found": len(expanded_edges),
            "relevant_tags": relevant_tags,
            "nodes": context_nodes,
        }
    }
