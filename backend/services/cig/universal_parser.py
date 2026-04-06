"""
Step 3 — Universal Parser (Tree-sitter)

Uses Tree-sitter for high-fidelity AST parsing of JavaScript and TypeScript.
Handles: JS, JSX, TS, TSX, MJS, CJS

OUTPUT FORMAT (same as python_parser):
{
    "file": "path/to/file.js",
    "functions": [...],
    "classes": [...],
    "imports": [...],
    "calls": [...]
}
"""

from tree_sitter import Language, Parser, Node
import tree_sitter_javascript as tsjs
import tree_sitter_typescript as tsts


# ── Language instances ────────────────────────────────────────────────────────

JS_LANGUAGE = Language(tsjs.language())
TS_LANGUAGE = Language(tsts.language_typescript())
TSX_LANGUAGE = Language(tsts.language_tsx())


def _get_language(extension: str) -> Language:
    """Pick the correct tree-sitter language for an extension."""
    ext = extension.lower()
    if ext in (".ts", ".mts", ".cts"):
        return TS_LANGUAGE
    elif ext in (".tsx", ".jsx"):
        return TSX_LANGUAGE
    else:
        return JS_LANGUAGE


# ── Main entry ────────────────────────────────────────────────────────────────


def parse_js_ts(source: str, file_path: str, extension: str = ".js") -> dict:
    """
    Parse a JavaScript/TypeScript file using Tree-sitter.
    Returns standardized output format.
    """
    lang = _get_language(extension)
    parser = Parser(lang)
    tree = parser.parse(source.encode("utf-8"))
    root = tree.root_node

    functions = []
    classes = []
    imports = []
    calls = []

    _walk_node(root, file_path, functions, classes, imports, calls)

    return {
        "file": file_path,
        "language": "typescript" if extension in (".ts", ".tsx", ".mts", ".cts") else "javascript",
        "functions": functions,
        "classes": classes,
        "imports": imports,
        "calls": calls,
    }


# ── AST Walker ────────────────────────────────────────────────────────────────


def _walk_node(node: Node, file_path: str,
               functions: list, classes: list,
               imports: list, calls: list,
               current_class: str | None = None):
    """Recursively walk the tree-sitter AST and extract entities."""

    ntype = node.type

    # ── Functions ─────────────────────────────────────────────────────────
    if ntype == "function_declaration":
        func = _extract_function_declaration(node, file_path, current_class)
        if func:
            functions.append(func)
            _extract_calls_from_body(node, file_path, func["name"], calls)
        return  # Don't recurse into function body for more declarations

    if ntype == "method_definition":
        func = _extract_method(node, file_path, current_class)
        if func:
            functions.append(func)
            _extract_calls_from_body(node, file_path,
                                     f"{current_class}.{func['name']}" if current_class else func["name"],
                                     calls)
        return

    # Arrow functions / function expressions assigned to variables
    if ntype == "lexical_declaration" or ntype == "variable_declaration":
        for declarator in _children_of_type(node, "variable_declarator"):
            name_node = declarator.child_by_field_name("name")
            value_node = declarator.child_by_field_name("value")
            if name_node and value_node and value_node.type in ("arrow_function", "function"):
                func = _extract_variable_function(name_node, value_node, file_path, current_class)
                if func:
                    functions.append(func)
                    caller = f"{current_class}.{func['name']}" if current_class else func["name"]
                    _extract_calls_from_body(value_node, file_path, caller, calls)
                continue
            # If not a function assignment, check for calls in the value
            if value_node:
                _extract_calls_from_body(value_node, file_path, "<module>", calls)

    # ── Classes ───────────────────────────────────────────────────────────
    if ntype == "class_declaration":
        cls = _extract_class(node, file_path)
        if cls:
            classes.append(cls)
            # Recurse into class body for methods
            body = node.child_by_field_name("body")
            if body:
                for child in body.children:
                    _walk_node(child, file_path, functions, classes, imports, calls,
                               current_class=cls["name"])
        return

    # ── Imports ───────────────────────────────────────────────────────────
    if ntype == "import_statement":
        imp = _extract_import(node, file_path)
        imports.extend(imp)
        return

    # ── require() calls (CommonJS) ────────────────────────────────────────
    if ntype == "expression_statement":
        _check_require(node, imports, file_path)

    # ── Export statements (may contain function/class declarations) ───────
    if ntype in ("export_statement", "export_default_declaration"):
        for child in node.children:
            _walk_node(child, file_path, functions, classes, imports, calls, current_class)
        return

    # ── Recurse into other nodes ──────────────────────────────────────────
    for child in node.children:
        _walk_node(child, file_path, functions, classes, imports, calls, current_class)


# ── Function Extractors ──────────────────────────────────────────────────────


def _extract_function_declaration(node: Node, file_path: str,
                                   class_name: str | None = None) -> dict | None:
    """Extract a `function name(...) {}` declaration."""
    name_node = node.child_by_field_name("name")
    if not name_node:
        return None

    name = name_node.text.decode("utf-8")
    params = _extract_params(node)
    is_async = any(c.type == "async" for c in node.children)

    qname = f"{file_path}::{class_name}.{name}" if class_name else f"{file_path}::{name}"

    return {
        "name": name,
        "qualified_name": qname,
        "file_path": file_path,
        "class_name": class_name,
        "params": params,
        "decorators": [],
        "is_async": is_async,
        "is_method": class_name is not None,
        "start_line": node.start_point[0] + 1,
        "end_line": node.end_point[0] + 1,
        "docstring": _extract_jsdoc(node),
    }


def _extract_method(node: Node, file_path: str,
                     class_name: str | None = None) -> dict | None:
    """Extract a class method definition."""
    name_node = node.child_by_field_name("name")
    if not name_node:
        return None

    name = name_node.text.decode("utf-8")
    params = _extract_params(node)
    is_async = any(c.type == "async" for c in node.children)

    # Check for decorators
    decorators = []
    prev = node.prev_sibling
    while prev and prev.type == "decorator":
        dec_text = prev.text.decode("utf-8").lstrip("@").strip()
        decorators.append(dec_text)
        prev = prev.prev_sibling

    qname = f"{file_path}::{class_name}.{name}" if class_name else f"{file_path}::{name}"

    return {
        "name": name,
        "qualified_name": qname,
        "file_path": file_path,
        "class_name": class_name,
        "params": params,
        "decorators": decorators,
        "is_async": is_async,
        "is_method": True,
        "start_line": node.start_point[0] + 1,
        "end_line": node.end_point[0] + 1,
        "docstring": _extract_jsdoc(node),
    }


def _extract_variable_function(name_node: Node, value_node: Node,
                                file_path: str,
                                class_name: str | None = None) -> dict | None:
    """Extract `const name = () => {}` or `const name = function() {}`."""
    name = name_node.text.decode("utf-8")
    params = _extract_params(value_node)
    is_async = any(c.type == "async" for c in value_node.children)

    qname = f"{file_path}::{class_name}.{name}" if class_name else f"{file_path}::{name}"

    return {
        "name": name,
        "qualified_name": qname,
        "file_path": file_path,
        "class_name": class_name,
        "params": params,
        "decorators": [],
        "is_async": is_async,
        "is_method": class_name is not None,
        "start_line": name_node.start_point[0] + 1,
        "end_line": value_node.end_point[0] + 1,
        "docstring": "",
    }


# ── Class Extractor ──────────────────────────────────────────────────────────


def _extract_class(node: Node, file_path: str) -> dict | None:
    """Extract a class declaration."""
    name_node = node.child_by_field_name("name")
    if not name_node:
        return None

    name = name_node.text.decode("utf-8")

    # Extract base classes (heritage / extends)
    bases = []
    heritage = node.child_by_field_name("heritage") or _find_child(node, "class_heritage")
    if heritage:
        for child in heritage.children:
            if child.type == "identifier" or child.type == "member_expression":
                bases.append(child.text.decode("utf-8"))

    # Check for decorators
    decorators = []
    prev = node.prev_sibling
    while prev and prev.type == "decorator":
        dec_text = prev.text.decode("utf-8").lstrip("@").strip()
        decorators.append(dec_text)
        prev = prev.prev_sibling

    return {
        "name": name,
        "qualified_name": f"{file_path}::{name}",
        "file_path": file_path,
        "bases": bases,
        "decorators": decorators,
        "start_line": node.start_point[0] + 1,
        "end_line": node.end_point[0] + 1,
        "docstring": _extract_jsdoc(node),
    }


# ── Import Extractors ────────────────────────────────────────────────────────


def _extract_import(node: Node, file_path: str) -> list[dict]:
    """Extract ES module import statement."""
    results = []
    source_node = node.child_by_field_name("source")
    if not source_node:
        # Try finding a string node
        for child in node.children:
            if child.type == "string":
                source_node = child
                break

    module = ""
    if source_node:
        module = source_node.text.decode("utf-8").strip("'\"")

    # Default import: import X from '...'
    # Named imports: import { X, Y } from '...'
    # Namespace import: import * as X from '...'
    for child in node.children:
        if child.type == "import_clause":
            for sub in child.children:
                if sub.type == "identifier":
                    # Default import
                    results.append({
                        "type": "default_import",
                        "module": module,
                        "name": sub.text.decode("utf-8"),
                        "alias": None,
                        "line": node.start_point[0] + 1,
                    })
                elif sub.type == "named_imports":
                    for spec in sub.children:
                        if spec.type == "import_specifier":
                            name_n = spec.child_by_field_name("name")
                            alias_n = spec.child_by_field_name("alias")
                            if name_n:
                                results.append({
                                    "type": "named_import",
                                    "module": module,
                                    "name": name_n.text.decode("utf-8"),
                                    "alias": alias_n.text.decode("utf-8") if alias_n else None,
                                    "line": node.start_point[0] + 1,
                                })
                elif sub.type == "namespace_import":
                    alias_node = _find_child(sub, "identifier")
                    results.append({
                        "type": "namespace_import",
                        "module": module,
                        "name": "*",
                        "alias": alias_node.text.decode("utf-8") if alias_node else None,
                        "line": node.start_point[0] + 1,
                    })

    # If no clause found but module exists, it's a side-effect import
    if not results and module:
        results.append({
            "type": "side_effect_import",
            "module": module,
            "name": None,
            "alias": None,
            "line": node.start_point[0] + 1,
        })

    return results


def _check_require(node: Node, imports: list, file_path: str):
    """Check for CommonJS require() calls."""
    text = node.text.decode("utf-8")
    if "require(" not in text:
        return

    # Walk to find call_expression with require
    for child in _walk_all(node):
        if child.type == "call_expression":
            func = child.child_by_field_name("function")
            if func and func.text.decode("utf-8") == "require":
                args = child.child_by_field_name("arguments")
                if args:
                    for arg in args.children:
                        if arg.type == "string":
                            module = arg.text.decode("utf-8").strip("'\"")
                            imports.append({
                                "type": "require",
                                "module": module,
                                "name": None,
                                "alias": None,
                                "line": node.start_point[0] + 1,
                            })


# ── Call Extractors ──────────────────────────────────────────────────────────


def _extract_calls_from_body(node: Node, file_path: str,
                              caller: str, calls: list):
    """Extract all function calls within a node (function body)."""
    for child in _walk_all(node):
        if child.type == "call_expression":
            func_node = child.child_by_field_name("function")
            if func_node:
                callee = func_node.text.decode("utf-8")
                # Skip built-in / noisy calls
                if callee in ("require", "console.log", "console.error",
                              "console.warn", "console.info"):
                    continue
                calls.append({
                    "caller": caller,
                    "callee": callee,
                    "file_path": file_path,
                    "line": child.start_point[0] + 1,
                })


# ── Helpers ──────────────────────────────────────────────────────────────────


def _extract_params(node: Node) -> list[str]:
    """Extract parameter names from a function/method node."""
    params = []
    param_node = node.child_by_field_name("parameters") or \
                 node.child_by_field_name("params")
    if not param_node:
        # For arrow functions, check for formal_parameters
        for child in node.children:
            if child.type in ("formal_parameters", "required_parameter",
                              "optional_parameter"):
                param_node = child
                break

    if param_node:
        for child in param_node.children:
            if child.type in ("identifier", "required_parameter",
                              "optional_parameter", "rest_pattern",
                              "assignment_pattern"):
                # Get the parameter name
                if child.type == "identifier":
                    params.append(child.text.decode("utf-8"))
                else:
                    # For complex params, get the first identifier
                    id_node = _find_child(child, "identifier")
                    if id_node:
                        params.append(id_node.text.decode("utf-8"))
    return params


def _extract_jsdoc(node: Node) -> str:
    """Extract JSDoc comment above a node."""
    prev = node.prev_sibling
    if prev and prev.type == "comment":
        text = prev.text.decode("utf-8")
        if text.startswith("/**"):
            return text[:500]
    return ""


def _find_child(node: Node, child_type: str) -> Node | None:
    """Find first direct child of a given type."""
    for child in node.children:
        if child.type == child_type:
            return child
    return None


def _children_of_type(node: Node, child_type: str) -> list[Node]:
    """Return all direct children of a given type."""
    return [c for c in node.children if c.type == child_type]


def _walk_all(node: Node):
    """Recursively yield all descendant nodes."""
    for child in node.children:
        yield child
        yield from _walk_all(child)
