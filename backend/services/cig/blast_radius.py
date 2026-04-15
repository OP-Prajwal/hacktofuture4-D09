"""
Blast Radius Calculator

Queries the Neo4j code intelligence graph to determine the impact
of changed files. Returns affected symbols, files, and test skip
recommendations for CI acceleration.
"""

from __future__ import annotations

from db.neo4j_db import neo4j_db


def calculate_blast_radius(project_path: str, changed_files: list[str]) -> dict:
    """
    Given a list of changed file paths, query the graph to find:
    - All symbols (functions/classes) in those files
    - All upstream dependents (d=1, d=2, d=3)
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

    # 1. Find all symbols in the changed files
    changed_symbols_query = """
    MATCH (n {project: $project})
    WHERE any(f IN $files WHERE n.file_path ENDS WITH f OR n.name ENDS WITH f)
    RETURN n.name AS name, n.file_path AS file_path, labels(n)[0] AS type,
           coalesce(n.blast_radius, 0) AS blast_radius
    ORDER BY blast_radius DESC
    """

    try:
        changed_nodes = neo4j_db.run_query(changed_symbols_query, {
            "project": project_path,
            "files": changed_files
        })
    except Exception as e:
        print(f"[BlastRadius] Query failed: {e}")
        changed_nodes = []

    if not changed_nodes:
        return {
            "changed_files": changed_files,
            "affected_symbols": [],
            "affected_files": changed_files,
            "unaffected_files": [],
            "risk_level": "UNKNOWN",
            "recommendation": "Could not find changed files in the graph. Run 'Sync Updated Graph' first."
        }

    changed_symbol_names = [n["name"] for n in changed_nodes if n.get("name")]

    # 2. Find d=1 direct callers/importers (WILL BREAK)
    d1_query = """
    MATCH (changed {project: $project})-[r]-(neighbor {project: $project})
    WHERE changed.name IN $symbols
      AND type(r) IN ['CALLS', 'IMPORTS', 'DEPENDS_ON', 'EXTENDS']
    RETURN DISTINCT neighbor.name AS name, neighbor.file_path AS file_path,
           labels(neighbor)[0] AS type, type(r) AS rel_type,
           1 AS depth
    """

    # 3. Find d=2 indirect dependents (LIKELY AFFECTED)
    d2_query = """
    MATCH (changed {project: $project})-[r1]-(d1 {project: $project})-[r2]-(d2 {project: $project})
    WHERE changed.name IN $symbols
      AND type(r1) IN ['CALLS', 'IMPORTS', 'DEPENDS_ON', 'EXTENDS']
      AND type(r2) IN ['CALLS', 'IMPORTS', 'DEPENDS_ON', 'EXTENDS']
      AND NOT d2.name IN $symbols
      AND d2.name <> d1.name
    RETURN DISTINCT d2.name AS name, d2.file_path AS file_path,
           labels(d2)[0] AS type, 2 AS depth
    """

    try:
        d1_nodes = neo4j_db.run_query(d1_query, {
            "project": project_path,
            "symbols": changed_symbol_names
        })
    except Exception:
        d1_nodes = []

    try:
        d2_nodes = neo4j_db.run_query(d2_query, {
            "project": project_path,
            "symbols": changed_symbol_names
        })
    except Exception:
        d2_nodes = []

    # 4. Get ALL files in the project
    all_files_query = """
    MATCH (n {project: $project})
    WHERE n.file_path IS NOT NULL
    RETURN DISTINCT n.file_path AS file_path
    """

    try:
        all_file_nodes = neo4j_db.run_query(all_files_query, {"project": project_path})
        all_files = set(n["file_path"] for n in all_file_nodes if n.get("file_path"))
    except Exception:
        all_files = set()

    # 5. Build the affected set
    affected_files = set(changed_files)
    affected_symbols = list(changed_symbol_names)

    d1_details = []
    for n in d1_nodes:
        if n.get("file_path"):
            affected_files.add(n["file_path"])
        if n.get("name") and n["name"] not in affected_symbols:
            affected_symbols.append(n["name"])
        d1_details.append({
            "name": n.get("name", "?"),
            "file": n.get("file_path", "?"),
            "type": n.get("type", "?"),
            "depth": 1,
            "risk": "WILL_BREAK"
        })

    d2_details = []
    for n in d2_nodes:
        if n.get("file_path"):
            affected_files.add(n["file_path"])
        d2_details.append({
            "name": n.get("name", "?"),
            "file": n.get("file_path", "?"),
            "type": n.get("type", "?"),
            "depth": 2,
            "risk": "LIKELY_AFFECTED"
        })

    # 6. Determine unaffected files (safe to skip)
    unaffected_files = sorted(all_files - affected_files)

    # 7. Risk level
    max_blast = max((n.get("blast_radius", 0) for n in changed_nodes), default=0)
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
