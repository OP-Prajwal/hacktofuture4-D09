"""
Step 4 — Symbol Registry

Global symbol table that tracks ALL declared symbols across the entire repository.
This is the foundation for cross-file reference resolution.

registry = {
    "function_name": "file_path",
    "ClassName": "file_path",
    ...
}
"""

from dataclasses import dataclass, field


@dataclass
class SymbolEntry:
    """A single symbol in the global registry."""
    name: str               # Symbol name (e.g. "register_user")
    qualified_name: str     # Full path (e.g. "services/auth_service.py::register_user")
    file_path: str          # Source file
    kind: str               # "function" | "class" | "method"
    class_name: str | None = None  # Parent class (if method)
    params: list = field(default_factory=list)
    line: int = 0
    exported: bool = True   # Is this symbol accessible from outside?


class SymbolRegistry:
    """
    Global symbol registry for the entire repository.
    
    Tracks all declared symbols and provides lookup by name.
    Handles ambiguity (same name in multiple files) via qualified names.
    """

    def __init__(self):
        # name → [SymbolEntry] (list for ambiguous names)
        self._by_name: dict[str, list[SymbolEntry]] = {}
        # qualified_name → SymbolEntry (unique)
        self._by_qualified: dict[str, SymbolEntry] = {}
        # file_path → [SymbolEntry] (all symbols in a file)
        self._by_file: dict[str, list[SymbolEntry]] = {}
        # module_path → file_path (import resolution)
        self._module_map: dict[str, str] = {}
        # file_path → [import_dict] (raw imports per file)
        self._imports: dict[str, list[dict]] = {}

    def register_function(self, func: dict):
        """Register a function/method from parser output."""
        entry = SymbolEntry(
            name=func["name"],
            qualified_name=func["qualified_name"],
            file_path=func["file_path"],
            kind="method" if func.get("is_method") else "function",
            class_name=func.get("class_name"),
            params=func.get("params", []),
            line=func.get("start_line", 0),
        )
        self._add(entry)

    def register_class(self, cls: dict):
        """Register a class from parser output."""
        entry = SymbolEntry(
            name=cls["name"],
            qualified_name=cls["qualified_name"],
            file_path=cls["file_path"],
            kind="class",
            line=cls.get("start_line", 0),
        )
        self._add(entry)

    def register_file(self, file_path: str):
        """Register a file path for module resolution."""
        # Create module path variants for import resolution
        # e.g. "services/auth_service.py" → "services.auth_service"
        #      "services/auth_service.py" → "services/auth_service"
        base = file_path
        for ext in (".py", ".js", ".ts", ".tsx", ".jsx", ".mjs", ".cjs"):
            if base.endswith(ext):
                base = base[:-len(ext)]
                break

        # Store multiple resolution paths
        self._module_map[base] = file_path
        self._module_map[base.replace("/", ".")] = file_path
        self._module_map[base.replace("\\", ".")] = file_path

        # Also store just the filename without extension
        parts = base.replace("\\", "/").split("/")
        if parts:
            self._module_map[parts[-1]] = file_path

    def register_imports(self, file_path: str, imports: list[dict]):
        """Store raw imports for a file (used by resolver)."""
        self._imports[file_path] = imports

    def lookup(self, name: str) -> list[SymbolEntry]:
        """Look up symbols by simple name. May return multiple matches."""
        return self._by_name.get(name, [])

    def lookup_qualified(self, qualified_name: str) -> SymbolEntry | None:
        """Look up a symbol by its unique qualified name."""
        return self._by_qualified.get(qualified_name)

    def lookup_in_file(self, file_path: str) -> list[SymbolEntry]:
        """Get all symbols declared in a specific file."""
        return self._by_file.get(file_path, [])

    def resolve_module(self, module_path: str) -> str | None:
        """Resolve a module import path to an actual file path."""
        # Direct match
        if module_path in self._module_map:
            return self._module_map[module_path]

        # Try without leading dots (relative imports)
        cleaned = module_path.lstrip(".")
        if cleaned in self._module_map:
            return self._module_map[cleaned]

        # Try adding common prefixes
        for prefix in ("", "src/", "lib/", "backend/", "services/"):
            candidate = prefix + cleaned
            if candidate in self._module_map:
                return self._module_map[candidate]
            if candidate.replace(".", "/") in self._module_map:
                return self._module_map[candidate.replace(".", "/")]

        return None

    def get_imports(self, file_path: str) -> list[dict]:
        """Get raw imports for a file."""
        return self._imports.get(file_path, [])

    def get_all_files(self) -> list[str]:
        """Get all registered file paths."""
        return list(self._by_file.keys())

    def get_all_symbols(self) -> list[SymbolEntry]:
        """Get every registered symbol."""
        return list(self._by_qualified.values())

    def get_stats(self) -> dict:
        """Return registry statistics."""
        all_syms = self.get_all_symbols()
        return {
            "total_symbols": len(all_syms),
            "functions": sum(1 for s in all_syms if s.kind == "function"),
            "methods": sum(1 for s in all_syms if s.kind == "method"),
            "classes": sum(1 for s in all_syms if s.kind == "class"),
            "files": len(self._by_file),
            "modules": len(self._module_map),
        }

    # ── Internal ──────────────────────────────────────────────────────────

    def _add(self, entry: SymbolEntry):
        """Add a symbol to all indices."""
        # By name (allow duplicates)
        if entry.name not in self._by_name:
            self._by_name[entry.name] = []
        self._by_name[entry.name].append(entry)

        # By qualified name (unique)
        self._by_qualified[entry.qualified_name] = entry

        # By file
        if entry.file_path not in self._by_file:
            self._by_file[entry.file_path] = []
        self._by_file[entry.file_path].append(entry)
