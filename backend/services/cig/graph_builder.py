"""
Step 6 — Graph Builder

Writes the parsed + resolved + enriched data into Neo4j.

NODES: Project, Module, File, Function, Class
EDGES: CONTAINS, CALLS, IMPORTS, EXTENDS, BELONGS_TO, DEPENDS_ON

Strategy: FULL REBUILD
  1. Delete entire project subgraph
  2. Rebuild from scratch
  → Deterministic, idempotent, always consistent
"""

from db.neo4j_db import neo4j_db
from .symbol_registry import SymbolRegistry
from .resolver import ResolvedCall, ResolvedImport, ResolvedInheritance


class GraphBuilder:
    """
    Constructs the Neo4j knowledge graph from parsed data.
    
    Uses MERGE for idempotency and batch operations for performance.
    """

    def __init__(self, workspace: str, project_name: str):
        self.workspace = workspace
        self.project_name = project_name
        self.project_path = f"{workspace}/{project_name}"
        self._stats = {
            "nodes_created": 0,
            "edges_created": 0,
            "files": 0,
            "functions": 0,
            "classes": 0,
            "calls": 0,
            "imports": 0,
            "extends": 0,
        }

    def build(self, parsed_files: list[dict],
              resolved: dict,
              registry: SymbolRegistry) -> dict:
        """
        Full graph build pipeline.
        
        1. Clear old graph
        2. Create Project node
        3. Create Module nodes
        4. Create File nodes
        5. Create Function + Class nodes
        6. Create all edges
        
        Returns build statistics.
        """
        print(f"\n[CIG] Building graph for {self.project_path}...")

        # Step 1: Clear old graph for this project
        self._clear_project_graph()

        # Step 2: Create Project node
        self._create_project_node()

        # Step 3: Create Module + File nodes with BELONGS_TO edges
        self._create_file_nodes(parsed_files)

        # Step 4: Create Function + Class nodes with CONTAINS edges
        self._create_entity_nodes(parsed_files)

        # Step 5: Create CALLS edges
        self._create_call_edges(resolved.get("calls", []))

        # Step 6: Create IMPORTS edges
        self._create_import_edges(resolved.get("imports", []))

        # Step 7: Create EXTENDS edges
        self._create_extends_edges(resolved.get("inheritance", []))

        # Step 8: Create DEPENDS_ON edges (module level)
        self._create_dependency_edges(resolved.get("imports", []))

        print(f"[CIG] Graph build complete: {self._stats}")
        return self._stats

    # ── Step 1: Clear ────────────────────────────────────────────────────────

    def _clear_project_graph(self):
        """Delete entire subgraph for this project."""
        print(f"[CIG] Clearing old graph for {self.project_path}...")
        try:
            # Delete all nodes connected to this project
            neo4j_db.run_query("""
                MATCH (p:Project {path: $path})
                OPTIONAL MATCH (p)-[*]->(n)
                DETACH DELETE n, p
            """, {"path": self.project_path})
        except Exception as e:
            print(f"[CIG] Warning: Could not clear graph (may be first run): {e}")

    # ── Step 2: Project Node ─────────────────────────────────────────────────

    def _create_project_node(self):
        """Create the root Project node."""
        try:
            neo4j_db.run_query("""
                MERGE (p:Project {path: $path})
                SET p.workspace = $workspace,
                    p.name = $name,
                    p.updated_at = datetime()
                RETURN p
            """, {
                "path": self.project_path,
                "workspace": self.workspace,
                "name": self.project_name,
            })
            self._stats["nodes_created"] += 1
        except Exception as e:
            print(f"[CIG] Error creating project node: {e}")

    # ── Step 3: File Nodes ───────────────────────────────────────────────────

    def _create_file_nodes(self, parsed_files: list[dict]):
        """Create File and Module nodes with BELONGS_TO edges."""
        modules_created = set()

        for pf in parsed_files:
            file_path = pf["file"]
            language = pf.get("language", "unknown")
            summary = pf.get("file_summary", "")
            tags = pf.get("file_tags", [])

            # Determine module (directory path)
            parts = file_path.replace("\\", "/").split("/")
            if len(parts) > 1:
                module_path = "/".join(parts[:-1])
            else:
                module_path = "root"

            # Create module if not yet created
            if module_path not in modules_created:
                try:
                    neo4j_db.run_query("""
                        MERGE (m:Module {path: $module_path, project: $project_path})
                        SET m.name = $name,
                            m.language = $language
                        WITH m
                        MATCH (p:Project {path: $project_path})
                        MERGE (m)-[:BELONGS_TO]->(p)
                    """, {
                        "module_path": module_path,
                        "project_path": self.project_path,
                        "name": module_path.split("/")[-1],
                        "language": language,
                    })
                    modules_created.add(module_path)
                    self._stats["nodes_created"] += 1
                except Exception as e:
                    print(f"[CIG] Error creating module {module_path}: {e}")

            # Create file node
            try:
                filename = parts[-1]
                extension = ""
                if "." in filename:
                    extension = "." + filename.rsplit(".", 1)[-1]

                neo4j_db.run_query("""
                    MERGE (f:File {path: $file_path, project: $project_path})
                    SET f.name = $name,
                        f.extension = $ext,
                        f.language = $language,
                        f.summary = $summary,
                        f.tags = $tags
                    WITH f
                    MATCH (m:Module {path: $module_path, project: $project_path})
                    MERGE (f)-[:BELONGS_TO]->(m)
                """, {
                    "file_path": file_path,
                    "project_path": self.project_path,
                    "name": filename,
                    "ext": extension,
                    "language": language,
                    "module_path": module_path,
                    "summary": summary,
                    "tags": tags,
                })
                self._stats["nodes_created"] += 1
                self._stats["files"] += 1
            except Exception as e:
                print(f"[CIG] Error creating file {file_path}: {e}")

    # ── Step 4: Entity Nodes ─────────────────────────────────────────────────

    def _create_entity_nodes(self, parsed_files: list[dict]):
        """Create Function and Class nodes with CONTAINS edges."""
        for pf in parsed_files:
            file_path = pf["file"]

            # Create function nodes
            for func in pf.get("functions", []):
                try:
                    neo4j_db.run_query("""
                        MERGE (fn:Function {qualified_name: $qname, project: $project_path})
                        SET fn.name = $name,
                            fn.file_path = $file_path,
                            fn.params = $params,
                            fn.is_async = $is_async,
                            fn.is_method = $is_method,
                            fn.start_line = $start_line,
                            fn.end_line = $end_line,
                            fn.summary = $summary,
                            fn.tags = $tags
                        WITH fn
                        MATCH (f:File {path: $file_path, project: $project_path})
                        MERGE (f)-[:CONTAINS]->(fn)
                    """, {
                        "qname": func["qualified_name"],
                        "project_path": self.project_path,
                        "name": func["name"],
                        "file_path": file_path,
                        "params": func.get("params", []),
                        "is_async": func.get("is_async", False),
                        "is_method": func.get("is_method", False),
                        "start_line": func.get("start_line", 0),
                        "end_line": func.get("end_line", 0),
                        "summary": func.get("summary", ""),
                        "tags": func.get("tags", []),
                    })
                    self._stats["nodes_created"] += 1
                    self._stats["functions"] += 1

                    # If it's a method, also link to its class
                    if func.get("class_name"):
                        class_qname = f"{file_path}::{func['class_name']}"
                        neo4j_db.run_query("""
                            MATCH (c:Class {qualified_name: $cqname, project: $project_path})
                            MATCH (fn:Function {qualified_name: $fqname, project: $project_path})
                            MERGE (c)-[:CONTAINS]->(fn)
                        """, {
                            "cqname": class_qname,
                            "fqname": func["qualified_name"],
                            "project_path": self.project_path,
                        })

                except Exception as e:
                    print(f"[CIG] Error creating function {func['name']}: {e}")

            # Create class nodes
            for cls in pf.get("classes", []):
                try:
                    neo4j_db.run_query("""
                        MERGE (c:Class {qualified_name: $qname, project: $project_path})
                        SET c.name = $name,
                            c.file_path = $file_path,
                            c.start_line = $start_line,
                            c.end_line = $end_line,
                            c.summary = $summary,
                            c.tags = $tags
                        WITH c
                        MATCH (f:File {path: $file_path, project: $project_path})
                        MERGE (f)-[:CONTAINS]->(c)
                    """, {
                        "qname": cls["qualified_name"],
                        "project_path": self.project_path,
                        "name": cls["name"],
                        "file_path": cls.get("file_path", ""),
                        "start_line": cls.get("start_line", 0),
                        "end_line": cls.get("end_line", 0),
                        "summary": cls.get("summary", ""),
                        "tags": cls.get("tags", []),
                    })
                    self._stats["nodes_created"] += 1
                    self._stats["classes"] += 1
                except Exception as e:
                    print(f"[CIG] Error creating class {cls['name']}: {e}")

    # ── Step 5: CALLS Edges ──────────────────────────────────────────────────

    def _create_call_edges(self, calls: list[ResolvedCall]):
        """Create Function -[CALLS]-> Function edges."""
        for call in calls:
            if not call.resolved:
                continue  # Skip unresolved calls

            try:
                neo4j_db.run_query("""
                    MATCH (caller:Function {qualified_name: $caller_qn, project: $project_path})
                    MATCH (callee:Function {qualified_name: $callee_qn, project: $project_path})
                    MERGE (caller)-[r:CALLS]->(callee)
                    SET r.line = $line, r.resolved = true
                """, {
                    "caller_qn": call.caller_qualified,
                    "callee_qn": call.callee_qualified,
                    "project_path": self.project_path,
                    "line": call.line,
                })
                self._stats["edges_created"] += 1
                self._stats["calls"] += 1
            except Exception as e:
                pass  # Silently skip failed edges

    # ── Step 6: IMPORTS Edges ────────────────────────────────────────────────

    def _create_import_edges(self, imports: list[ResolvedImport]):
        """Create File -[IMPORTS]-> File edges."""
        for imp in imports:
            if not imp.resolved:
                continue

            try:
                neo4j_db.run_query("""
                    MATCH (src:File {path: $source, project: $project_path})
                    MATCH (tgt:File {path: $target, project: $project_path})
                    MERGE (src)-[r:IMPORTS]->(tgt)
                    SET r.symbols = $symbols
                """, {
                    "source": imp.source_file,
                    "target": imp.target_file,
                    "project_path": self.project_path,
                    "symbols": imp.symbols,
                })
                self._stats["edges_created"] += 1
                self._stats["imports"] += 1
            except Exception as e:
                pass

    # ── Step 7: EXTENDS Edges ────────────────────────────────────────────────

    def _create_extends_edges(self, inheritance: list[ResolvedInheritance]):
        """Create Class -[EXTENDS]-> Class edges."""
        for inh in inheritance:
            if not inh.resolved:
                continue

            try:
                neo4j_db.run_query("""
                    MATCH (child:Class {qualified_name: $child_qn, project: $project_path})
                    MATCH (parent:Class {qualified_name: $parent_qn, project: $project_path})
                    MERGE (child)-[r:EXTENDS]->(parent)
                """, {
                    "child_qn": inh.child_qualified,
                    "parent_qn": inh.parent_qualified,
                    "project_path": self.project_path,
                })
                self._stats["edges_created"] += 1
                self._stats["extends"] += 1
            except Exception as e:
                pass

    # ── Step 8: DEPENDS_ON Edges ─────────────────────────────────────────────

    def _create_dependency_edges(self, imports: list[ResolvedImport]):
        """Create Module -[DEPENDS_ON]-> Module edges from resolved imports."""
        module_deps: set[tuple[str, str]] = set()

        for imp in imports:
            if not imp.resolved:
                continue

            # Extract module paths from file paths
            src_parts = imp.source_file.replace("\\", "/").split("/")
            tgt_parts = imp.target_file.replace("\\", "/").split("/")

            src_module = "/".join(src_parts[:-1]) if len(src_parts) > 1 else "root"
            tgt_module = "/".join(tgt_parts[:-1]) if len(tgt_parts) > 1 else "root"

            if src_module != tgt_module:
                module_deps.add((src_module, tgt_module))

        for src_mod, tgt_mod in module_deps:
            try:
                neo4j_db.run_query("""
                    MATCH (src:Module {path: $source, project: $project_path})
                    MATCH (tgt:Module {path: $target, project: $project_path})
                    MERGE (src)-[:DEPENDS_ON]->(tgt)
                """, {
                    "source": src_mod,
                    "target": tgt_mod,
                    "project_path": self.project_path,
                })
                self._stats["edges_created"] += 1
            except Exception as e:
                pass
