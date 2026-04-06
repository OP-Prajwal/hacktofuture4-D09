"""
Step 5 — Resolver

Resolves cross-file references using the global symbol registry.

Resolves:
  1. Function calls → actual function definitions
  2. Import paths → actual files
  3. Class inheritance → actual base classes
"""

from .symbol_registry import SymbolRegistry


class ResolvedCall:
    """A resolved function call edge."""
    __slots__ = ("caller_qualified", "callee_qualified",
                 "caller_file", "callee_file", "line", "resolved")

    def __init__(self, caller_qualified: str, callee_qualified: str,
                 caller_file: str, callee_file: str, line: int, resolved: bool):
        self.caller_qualified = caller_qualified
        self.callee_qualified = callee_qualified
        self.caller_file = caller_file
        self.callee_file = callee_file
        self.line = line
        self.resolved = resolved


class ResolvedImport:
    """A resolved file-to-file import edge."""
    __slots__ = ("source_file", "target_file", "symbols", "resolved")

    def __init__(self, source_file: str, target_file: str,
                 symbols: list[str], resolved: bool):
        self.source_file = source_file
        self.target_file = target_file
        self.symbols = symbols
        self.resolved = resolved


class ResolvedInheritance:
    """A resolved class inheritance edge."""
    __slots__ = ("child_qualified", "parent_qualified",
                 "child_file", "parent_file", "resolved")

    def __init__(self, child_qualified: str, parent_qualified: str,
                 child_file: str, parent_file: str, resolved: bool):
        self.child_qualified = child_qualified
        self.parent_qualified = parent_qualified
        self.child_file = child_file
        self.parent_file = parent_file
        self.resolved = resolved


class Resolver:
    """
    Cross-file reference resolver.
    
    Takes parsed data + symbol registry and resolves all cross-file
    relationships into concrete edges.
    """

    def __init__(self, registry: SymbolRegistry):
        self.registry = registry

    def resolve_all(self, parsed_files: list[dict]) -> dict:
        """
        Resolve all cross-file references.
        
        Returns:
        {
            "calls": [ResolvedCall, ...],
            "imports": [ResolvedImport, ...],
            "inheritance": [ResolvedInheritance, ...]
        }
        """
        resolved_calls = []
        resolved_imports = []
        resolved_inheritance = []

        for pf in parsed_files:
            file_path = pf["file"]

            # ── Resolve calls ─────────────────────────────────────────────
            for call in pf.get("calls", []):
                rc = self._resolve_call(call, file_path)
                resolved_calls.append(rc)

            # ── Resolve imports ───────────────────────────────────────────
            for imp in pf.get("imports", []):
                ri = self._resolve_import(imp, file_path)
                if ri:
                    resolved_imports.append(ri)

            # ── Resolve class inheritance ─────────────────────────────────
            for cls in pf.get("classes", []):
                for base in cls.get("bases", []):
                    rh = self._resolve_inheritance(cls, base, file_path)
                    resolved_inheritance.append(rh)

        # Deduplicate imports (same source → target)
        resolved_imports = self._dedupe_imports(resolved_imports)

        return {
            "calls": resolved_calls,
            "imports": resolved_imports,
            "inheritance": resolved_inheritance,
        }

    # ── Call Resolution ──────────────────────────────────────────────────────

    def _resolve_call(self, call: dict, file_path: str) -> ResolvedCall:
        """
        Resolve a function call to its definition.
        
        Strategy:
        1. Check if callee matches an imported symbol in this file
        2. Check if callee matches a symbol in the same file
        3. Check global registry for a unique match
        4. Handle method calls (obj.method)
        """
        callee = call["callee"]
        caller = call["caller"]
        line = call.get("line", 0)

        # Build caller qualified name
        caller_qualified = f"{file_path}::{caller}"

        # Handle method calls: "obj.method" → try to find "method"
        method_name = callee.split(".")[-1] if "." in callee else callee

        # 1. Try imported symbols first
        file_imports = self.registry.get_imports(file_path)
        for imp in file_imports:
            imp_name = imp.get("alias") or imp.get("name")
            if imp_name == callee or imp_name == method_name:
                # Resolve the import's module to a file
                target_file = self.registry.resolve_module(imp["module"])
                if target_file:
                    # Find the symbol in that file
                    symbols = self.registry.lookup_in_file(target_file)
                    for sym in symbols:
                        if sym.name == method_name:
                            return ResolvedCall(
                                caller_qualified=caller_qualified,
                                callee_qualified=sym.qualified_name,
                                caller_file=file_path,
                                callee_file=target_file,
                                line=line,
                                resolved=True,
                            )

        # 2. Check same file
        same_file_symbols = self.registry.lookup_in_file(file_path)
        for sym in same_file_symbols:
            if sym.name == method_name:
                return ResolvedCall(
                    caller_qualified=caller_qualified,
                    callee_qualified=sym.qualified_name,
                    caller_file=file_path,
                    callee_file=file_path,
                    line=line,
                    resolved=True,
                )

        # 3. Global lookup
        matches = self.registry.lookup(method_name)
        if len(matches) == 1:
            sym = matches[0]
            return ResolvedCall(
                caller_qualified=caller_qualified,
                callee_qualified=sym.qualified_name,
                caller_file=file_path,
                callee_file=sym.file_path,
                line=line,
                resolved=True,
            )

        # 4. Unresolved — store with best guess
        callee_qualified = f"<unresolved>::{callee}"
        return ResolvedCall(
            caller_qualified=caller_qualified,
            callee_qualified=callee_qualified,
            caller_file=file_path,
            callee_file="",
            line=line,
            resolved=False,
        )

    # ── Import Resolution ────────────────────────────────────────────────────

    def _resolve_import(self, imp: dict, source_file: str) -> ResolvedImport | None:
        """Resolve an import statement to its target file."""
        module = imp.get("module", "")
        if not module:
            return None

        target_file = self.registry.resolve_module(module)
        symbols = []
        if imp.get("name"):
            symbols.append(imp["name"])

        return ResolvedImport(
            source_file=source_file,
            target_file=target_file or module,  # Keep raw module if unresolved
            symbols=symbols,
            resolved=target_file is not None,
        )

    # ── Inheritance Resolution ───────────────────────────────────────────────

    def _resolve_inheritance(self, cls: dict, base_name: str,
                              file_path: str) -> ResolvedInheritance:
        """Resolve a class inheritance to its base class definition."""
        child_qualified = cls["qualified_name"]

        # Look up the base class
        matches = self.registry.lookup(base_name)
        for sym in matches:
            if sym.kind == "class":
                return ResolvedInheritance(
                    child_qualified=child_qualified,
                    parent_qualified=sym.qualified_name,
                    child_file=file_path,
                    parent_file=sym.file_path,
                    resolved=True,
                )

        return ResolvedInheritance(
            child_qualified=child_qualified,
            parent_qualified=f"<unresolved>::{base_name}",
            child_file=file_path,
            parent_file="",
            resolved=False,
        )

    # ── Deduplication ────────────────────────────────────────────────────────

    def _dedupe_imports(self, imports: list[ResolvedImport]) -> list[ResolvedImport]:
        """Merge duplicate import edges (same source → target)."""
        seen: dict[tuple, ResolvedImport] = {}
        for imp in imports:
            key = (imp.source_file, imp.target_file)
            if key in seen:
                # Merge symbols
                existing = seen[key]
                for s in imp.symbols:
                    if s not in existing.symbols:
                        existing.symbols.append(s)
                if imp.resolved:
                    existing.resolved = True
            else:
                seen[key] = imp
        return list(seen.values())
