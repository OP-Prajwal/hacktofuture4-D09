"""
Step 8 — Semantic Enricher

Generates semantic meaning for each graph node:
  - summary: concise natural language description
  - tags: categorization labels

Uses rule-based heuristics (deterministic, no LLM dependency).
LLM integration (qwen2.5-coder:3b) can be added in Phase 2.
"""

import re


import requests

# ── LLM Integration (Phase 2) ────────────────────────────────────────────────
# Configured for local qwen2.5-coder:3b
LLM_ENDPOINT = "http://localhost:11434/api/generate"
# Set to True locally if Ollama + qwen2.5-coder:3b is running
USE_LLM = True

def _llm_summarize(function_source: str) -> str:
    """Generate summary using local qwen2.5-coder:3b."""
    if not USE_LLM:
        return ""
    try:
        response = requests.post(LLM_ENDPOINT, json={
            "model": "qwen2.5-coder:3b",
            "prompt": f"Explain this function concisely in one sentence:\n\n{function_source}",
            "stream": False
        }, timeout=5.0)
        return response.json().get("response", "").strip()
    except Exception:
        return ""

# ── Tag Rules ─────────────────────────────────────────────────────────────────
# Each rule: (keywords_to_match, tag_to_assign)

TAG_RULES: list[tuple[list[str], str]] = [
    # API / Web
    (["route", "endpoint", "api", "rest", "graphql", "router",
      "get", "post", "put", "delete", "patch", "app.get", "app.post",
      "fastapi", "flask", "express", "handler", "middleware"], "API"),

    # Authentication / Security
    (["auth", "login", "logout", "register", "signup", "signin",
      "token", "jwt", "password", "hash", "encrypt", "decrypt",
      "session", "permission", "role", "credential", "oauth",
      "security", "verify", "bcrypt"], "Authentication"),

    # Database / Storage
    (["db", "database", "mongo", "neo4j", "sql", "query", "collection",
      "model", "schema", "migrate", "seed", "gridfs", "redis",
      "repository", "orm", "crud", "insert", "update", "find",
      "commit", "transaction"], "Database"),

    # Data Processing / ETL
    (["parse", "transform", "process", "convert", "normalize",
      "extract", "load", "pipeline", "clean", "filter", "map",
      "reduce", "aggregate", "batch", "stream", "serialize",
      "deserialize", "encode", "decode"], "Data Processing"),

    # ML / AI
    (["train", "model", "predict", "inference", "neural", "tensor",
      "epoch", "loss", "optimizer", "dataset", "feature", "embedding",
      "classifier", "regressor", "fit", "evaluate", "llm", "ai",
      "transformer", "attention", "bert", "gpt"], "Machine Learning"),

    # UI / Frontend
    (["component", "render", "jsx", "tsx", "react", "vue", "angular",
      "template", "style", "css", "layout", "page", "view",
      "button", "form", "input", "modal", "dialog", "sidebar",
      "navbar", "header", "footer", "dashboard", "onboarding"], "UI Component"),

    # Testing
    (["test", "spec", "mock", "stub", "assert", "expect", "describe",
      "it", "jest", "pytest", "unittest", "fixture"], "Testing"),

    # Configuration / Setup
    (["config", "setup", "init", "initialize", "env", "setting",
      "option", "constant", "default"], "Configuration"),

    # Utility / Helper
    (["util", "helper", "tool", "common", "shared", "lib",
      "format", "validate", "sanitize", "check", "is_", "has_",
      "get_", "set_"], "Utility"),

    # Routing / Navigation
    (["route", "router", "navigate", "redirect", "path", "url",
      "link", "history", "location"], "Routing"),

    # File / IO
    (["file", "read", "write", "stream", "upload", "download",
      "blob", "buffer", "fs", "path", "directory"], "File I/O"),

    # Error Handling
    (["error", "exception", "catch", "throw", "raise", "handle",
      "retry", "fallback", "recover"], "Error Handling"),

    # Logging / Monitoring
    (["log", "logger", "monitor", "trace", "metric", "alert",
      "sentry", "debug", "info", "warn"], "Logging"),

    # Graph / Intelligence
    (["graph", "node", "edge", "vertex", "relationship", "traverse",
      "cypher", "walker", "visitor", "ast", "parse", "tree"], "Graph Intelligence"),
]


def enrich_function(func: dict) -> dict:
    """
    Add semantic summary and tags to a function entity.
    Returns the same dict with 'summary' and 'tags' added.
    """
    name = func.get("name", "")
    docstring = func.get("docstring", "")
    file_path = func.get("file_path", "")
    params = func.get("params", [])
    decorators = func.get("decorators", [])
    source = func.get("source", "")

    # Build context string for tag matching
    context = f"{name} {docstring} {file_path} {' '.join(params)} {' '.join(decorators)}".lower()

    # Generate tags
    tags = _match_tags(context)

    # Generate summary (Prefer LLM if available, otherwise heuristic)
    summary = ""
    if USE_LLM and source:
        # Don't send huge functions to LLM to avoid timeout
        if len(source) < 5000:
            summary = _llm_summarize(source)
    
    if not summary:
        summary = _generate_summary(func, tags)

    func["summary"] = summary
    func["tags"] = tags
    return func


def enrich_class(cls: dict) -> dict:
    """Add semantic summary and tags to a class entity."""
    name = cls.get("name", "")
    docstring = cls.get("docstring", "")
    file_path = cls.get("file_path", "")
    bases = cls.get("bases", [])

    context = f"{name} {docstring} {file_path} {' '.join(bases)}".lower()

    tags = _match_tags(context)
    summary = _generate_class_summary(cls, tags)

    cls["summary"] = summary
    cls["tags"] = tags
    return cls


def enrich_node(node_data: dict, node_type: str) -> dict:
    """
    General entry point for enrichment.
    Takes a dictionary of node data and returns it enriched.
    """
    if node_type == "Function":
        return enrich_function(node_data)
    elif node_type == "Class":
        return enrich_class(node_data)
    elif node_type == "File":
        # For files, we assume all_tags might be empty unless provided
        return enrich_file(
            node_data.get("path", ""),
            node_data.get("language", "unknown"),
            node_data.get("num_functions", 0),
            node_data.get("num_classes", 0),
            node_data.get("child_tags", [])
        )
    return node_data


def enrich_file(file_path: str, language: str,
                num_functions: int, num_classes: int,
                all_tags: list[str]) -> dict:
    """Generate file-level enrichment."""
    context = file_path.lower()
    tags = _match_tags(context)

    # Merge with child tags (tags from functions/classes in this file)
    for t in all_tags:
        if t not in tags:
            tags.append(t)

    # Keep top 5 most relevant tags
    tags = tags[:5]

    summary = _generate_file_summary(file_path, language, num_functions, num_classes)

    return {
        "summary": summary,
        "tags": tags,
    }


# ── Internal ──────────────────────────────────────────────────────────────────


def _match_tags(context: str) -> list[str]:
    """Match context string against tag rules."""
    matched = []
    for keywords, tag in TAG_RULES:
        for kw in keywords:
            if kw in context:
                if tag not in matched:
                    matched.append(tag)
                break
    return matched


def _generate_summary(func: dict, tags: list[str]) -> str:
    """Generate a human-readable summary for a function."""
    name = func["name"]
    params = func.get("params", [])
    is_async = func.get("is_async", False)
    is_method = func.get("is_method", False)
    class_name = func.get("class_name")
    docstring = func.get("docstring", "")

    # If there's a docstring, use its first line
    if docstring:
        first_line = docstring.strip().split("\n")[0]
        # Clean up JSDoc or Python docstring formatting
        first_line = re.sub(r'^[/\*\s]+', '', first_line)
        first_line = re.sub(r'["\']', '', first_line).strip()
        if first_line and len(first_line) > 10:
            return first_line[:200]

    # Auto-generate from name
    parts = []
    if is_async:
        parts.append("Async")
    if is_method and class_name:
        parts.append(f"method of {class_name}")
    else:
        parts.append("function")

    # Humanize the function name
    readable = _humanize(name)
    parts.append(f"that {readable}")

    if params:
        param_str = ", ".join(p for p in params if p not in ("self", "cls"))
        if param_str:
            parts.append(f"(params: {param_str})")

    if tags:
        parts.append(f"[{', '.join(tags[:3])}]")

    return " ".join(parts)


def _generate_class_summary(cls: dict, tags: list[str]) -> str:
    """Generate a human-readable summary for a class."""
    name = cls["name"]
    bases = cls.get("bases", [])
    docstring = cls.get("docstring", "")

    if docstring:
        first_line = docstring.strip().split("\n")[0]
        first_line = re.sub(r'^[/\*\s]+', '', first_line)
        first_line = re.sub(r'["\']', '', first_line).strip()
        if first_line and len(first_line) > 10:
            return first_line[:200]

    readable = _humanize(name)
    summary = f"Class {name}: {readable}"
    if bases:
        summary += f" (extends {', '.join(bases)})"
    if tags:
        summary += f" [{', '.join(tags[:3])}]"
    return summary


def _generate_file_summary(file_path: str, language: str,
                           num_functions: int, num_classes: int) -> str:
    """Generate a human-readable summary for a file."""
    filename = file_path.replace("\\", "/").split("/")[-1]
    parts = [f"{filename}:"]

    if language != "unknown":
        parts.append(f"{language} module")
    else:
        parts.append("file")

    if num_functions or num_classes:
        parts.append("containing")
        items = []
        if num_functions:
            items.append(f"{num_functions} function(s)")
        if num_classes:
            items.append(f"{num_classes} class(es)")
        parts.append(" and ".join(items))

    return " ".join(parts)


def _humanize(name: str) -> str:
    """Convert a function/class name to human-readable text."""
    # snake_case → words
    if "_" in name:
        words = name.split("_")
        words = [w for w in words if w]  # Remove empty strings
        return " ".join(words)

    # camelCase / PascalCase → words
    words = re.sub(r'([A-Z])', r' \1', name).strip().lower().split()
    return " ".join(words)
