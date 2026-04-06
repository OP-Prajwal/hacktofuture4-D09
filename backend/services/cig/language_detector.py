"""
Step 2 — Language Detection

Maps file extensions to language identifiers.
Determines which parser to use for each file.
"""

EXTENSION_MAP = {
    # Python
    ".py":   "python",
    ".pyw":  "python",
    ".pyi":  "python",

    # JavaScript
    ".js":   "javascript",
    ".mjs":  "javascript",
    ".cjs":  "javascript",
    ".jsx":  "javascript",

    # TypeScript
    ".ts":   "typescript",
    ".tsx":  "typescript",
    ".mts":  "typescript",
    ".cts":  "typescript",

    # Web
    ".html": "html",
    ".css":  "css",
    ".scss": "css",
    ".less": "css",

    # Data / Config
    ".json": "json",
    ".yaml": "yaml",
    ".yml":  "yaml",
    ".toml": "toml",
    ".xml":  "xml",
    ".env":  "dotenv",

    # Docs
    ".md":   "markdown",
    ".rst":  "markdown",
    ".txt":  "text",

    # Other languages (future tree-sitter support)
    ".go":    "go",
    ".rs":    "rust",
    ".java":  "java",
    ".kt":    "kotlin",
    ".rb":    "ruby",
    ".php":   "php",
    ".c":     "c",
    ".cpp":   "cpp",
    ".h":     "c",
    ".hpp":   "cpp",
    ".cs":    "csharp",
    ".swift": "swift",
    ".sh":    "shell",
    ".bash":  "shell",
    ".sql":   "sql",
}

# Languages we can fully parse with AST
PARSEABLE_LANGUAGES = {"python", "javascript", "typescript"}

# Languages that use tree-sitter
TREESITTER_LANGUAGES = {"javascript", "typescript"}


def detect_language(extension: str) -> str:
    """Detect programming language from file extension."""
    return EXTENSION_MAP.get(extension.lower(), "unknown")


def is_parseable(extension: str) -> bool:
    """Check if we have a full AST parser for this language."""
    lang = detect_language(extension)
    return lang in PARSEABLE_LANGUAGES


def get_parser_type(extension: str) -> str:
    """
    Determine which parser to use:
    - 'ast'         → Python built-in ast module
    - 'treesitter'  → Tree-sitter (JS/TS)
    - 'generic'     → File-level metadata only
    """
    lang = detect_language(extension)
    if lang == "python":
        return "ast"
    elif lang in TREESITTER_LANGUAGES:
        return "treesitter"
    else:
        return "generic"
