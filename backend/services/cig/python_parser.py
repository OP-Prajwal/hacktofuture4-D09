"""
Step 3 — Python Parser (ast module)

Full-fidelity parsing using Python's built-in ast module.
Extracts: functions, classes, imports, function calls.

OUTPUT FORMAT:
{
    "file": "path/to/file.py",
    "functions": [...],
    "classes": [...],
    "imports": [...],
    "calls": [...]
}
"""

import ast
from typing import Any


def parse_python(source: str, file_path: str) -> dict:
    """
    Parse a Python file and extract all entities.
    
    Returns standardized output format with functions, classes, imports, calls.
    """
    try:
        tree = ast.parse(source, filename=file_path)
    except SyntaxError:
        return _empty_result(file_path)

    functions = []
    classes = []
    imports = []
    calls = []

    # ── Top-level walk ────────────────────────────────────────────────────
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func = _extract_function(node, file_path)
            functions.append(func)
            # Extract calls inside this function
            calls.extend(_extract_calls(node, file_path, func["name"]))

        elif isinstance(node, ast.ClassDef):
            cls = _extract_class(node, file_path)
            classes.append(cls)
            # Extract methods and their calls
            for item in ast.iter_child_nodes(node):
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    method = _extract_function(item, file_path, class_name=node.name)
                    functions.append(method)
                    calls.extend(_extract_calls(item, file_path, f"{node.name}.{item.name}"))

        elif isinstance(node, ast.Import):
            imports.extend(_extract_import(node))

        elif isinstance(node, ast.ImportFrom):
            imports.extend(_extract_import_from(node))

    return {
        "file": file_path,
        "language": "python",
        "functions": functions,
        "classes": classes,
        "imports": imports,
        "calls": calls,
    }


# ── Entity Extractors ────────────────────────────────────────────────────────


def _extract_function(node: ast.FunctionDef | ast.AsyncFunctionDef,
                      file_path: str,
                      class_name: str | None = None) -> dict:
    """Extract function/method metadata."""
    params = []
    for arg in node.args.args:
        params.append(arg.arg)
    for arg in node.args.kwonlyargs:
        params.append(arg.arg)
    if node.args.vararg:
        params.append(f"*{node.args.vararg.arg}")
    if node.args.kwarg:
        params.append(f"**{node.args.kwarg.arg}")

    decorators = []
    for dec in node.decorator_list:
        if isinstance(dec, ast.Name):
            decorators.append(dec.id)
        elif isinstance(dec, ast.Attribute):
            decorators.append(ast.unparse(dec))
        elif isinstance(dec, ast.Call):
            if isinstance(dec.func, ast.Name):
                decorators.append(dec.func.id)
            elif isinstance(dec.func, ast.Attribute):
                decorators.append(ast.unparse(dec.func))

    # Build qualified name
    if class_name:
        qualified_name = f"{file_path}::{class_name}.{node.name}"
    else:
        qualified_name = f"{file_path}::{node.name}"

    # Get docstring
    docstring = ast.get_docstring(node) or ""

    return {
        "name": node.name,
        "qualified_name": qualified_name,
        "file_path": file_path,
        "class_name": class_name,
        "params": params,
        "decorators": decorators,
        "is_async": isinstance(node, ast.AsyncFunctionDef),
        "is_method": class_name is not None,
        "start_line": node.lineno,
        "end_line": node.end_lineno or node.lineno,
        "docstring": docstring[:500],  # Truncate long docstrings
    }


def _extract_class(node: ast.ClassDef, file_path: str) -> dict:
    """Extract class metadata."""
    bases = []
    for base in node.bases:
        if isinstance(base, ast.Name):
            bases.append(base.id)
        elif isinstance(base, ast.Attribute):
            bases.append(ast.unparse(base))

    decorators = []
    for dec in node.decorator_list:
        if isinstance(dec, ast.Name):
            decorators.append(dec.id)
        elif isinstance(dec, ast.Attribute):
            decorators.append(ast.unparse(dec))

    docstring = ast.get_docstring(node) or ""

    return {
        "name": node.name,
        "qualified_name": f"{file_path}::{node.name}",
        "file_path": file_path,
        "bases": bases,
        "decorators": decorators,
        "start_line": node.lineno,
        "end_line": node.end_lineno or node.lineno,
        "docstring": docstring[:500],
    }


def _extract_import(node: ast.Import) -> list[dict]:
    """Extract `import X` statements."""
    results = []
    for alias in node.names:
        results.append({
            "type": "import",
            "module": alias.name,
            "name": alias.name,
            "alias": alias.asname,
            "line": node.lineno,
        })
    return results


def _extract_import_from(node: ast.ImportFrom) -> list[dict]:
    """Extract `from X import Y` statements."""
    module = node.module or ""
    results = []
    for alias in node.names:
        results.append({
            "type": "from_import",
            "module": module,
            "name": alias.name,
            "alias": alias.asname,
            "line": node.lineno,
            "level": node.level,  # relative import depth
        })
    return results


def _extract_calls(node: ast.AST, file_path: str, caller: str) -> list[dict]:
    """Extract all function/method calls within a function body."""
    calls = []
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            call_name = _get_call_name(child)
            if call_name:
                calls.append({
                    "caller": caller,
                    "callee": call_name,
                    "file_path": file_path,
                    "line": child.lineno,
                })
    return calls


def _get_call_name(node: ast.Call) -> str | None:
    """Extract the name of a function call."""
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    elif isinstance(func, ast.Attribute):
        # e.g. obj.method() → "obj.method"
        return ast.unparse(func)
    return None


def _empty_result(file_path: str) -> dict:
    """Return empty result for unparseable files."""
    return {
        "file": file_path,
        "language": "python",
        "functions": [],
        "classes": [],
        "imports": [],
        "calls": [],
    }
