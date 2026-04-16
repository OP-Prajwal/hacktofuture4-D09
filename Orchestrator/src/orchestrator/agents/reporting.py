from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from orchestrator.llm import OrchestratorLLM
from orchestrator.state import OrchestratorState


LANGUAGE_BY_EXTENSION = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".java": "java",
    ".rb": "ruby",
}


def write_report(state: OrchestratorState, output_dir: Path, llm: OrchestratorLLM) -> OrchestratorState:
    incident = state["incident"]
    locations = state.get("locations", [])

    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"{incident.id}.md"

    # ── 1. Extract the crashing file DIRECTLY from the stack trace ────────────
    # The stack trace is ground truth — always prefer it over graph text-search.
    stack_trace = incident.stack_trace or ""
    crash_file_from_trace: str | None = None
    crash_line_no: int | None = None

    if stack_trace:
        import re
        # Find all `File "...", line N` entries in the stack trace
        # The LAST one before the error is the actual crash site
        trace_matches = re.findall(
            r'File "([^"]+)",\s+line\s+(\d+)',
            stack_trace,
        )
        if trace_matches:
            raw_path, raw_line = trace_matches[-1]
            crash_line_no = int(raw_line)
            # Convert absolute runner path → repo-relative path
            # e.g. /home/runner/work/devopstest/devopstest/auth.py → auth.py
            crash_file_from_trace = re.sub(
                r"^.*/(?:work/[^/]+/[^/]+|devopstest)/", "", raw_path
            )

    # ── 2. Pick the best location entry for the crash file ────────────────────
    NOISE = (".json", ".txt", ".md", ".yml", ".yaml", ".toml", ".cfg", ".ini",
             ".lock", ".sample")

    source_location = None
    if crash_file_from_trace:
        # Try to find matching location entry for metadata (blast_radius, rationale etc.)
        fname = crash_file_from_trace.split("/")[-1]
        source_location = next(
            (loc for loc in locations if loc.path.endswith(fname)),
            None,
        )
        # If not in graph, synthesise a minimal location object
        if source_location is None:
            from orchestrator.models import CodeLocation
            source_location = CodeLocation(
                path=crash_file_from_trace,
                confidence=0.99,
                rationale="extracted directly from stack trace",
            )
    else:
        # Fall back to first non-noise graph location
        source_location = next(
            (loc for loc in locations if not any(loc.path.endswith(n) for n in NOISE)),
            locations[0] if locations else None,
        )

    language = _detect_language(source_location.path if source_location else "")
    code_fence = _code_fence(language)

    # ── 3. Read real source file & show crash-line context ────────────────────
    source_snippet = ""
    source_file_content = ""

    repo_root: Path | None = state.get("repo_root")

    if source_location and repo_root:
        candidate = repo_root / source_location.path
        if candidate.exists():
            try:
                source_file_content = candidate.read_text(encoding="utf-8")
                raw_lines = source_file_content.splitlines()
                if crash_line_no:
                    start = max(0, crash_line_no - 5)
                    end = min(len(raw_lines), crash_line_no + 4)
                    snippet_lines = []
                    for i, line in enumerate(raw_lines[start:end], start=start + 1):
                        marker = ">>> " if i == crash_line_no else "    "
                        snippet_lines.append(f"{marker}{i:4d} | {line}")
                    source_snippet = "\n".join(snippet_lines)
                else:
                    source_snippet = "\n".join(
                        f"    {i+1:4d} | {l}" for i, l in enumerate(raw_lines[:30])
                    )
            except Exception:
                pass

    # ── 3. Generate all possible fixes ─────────────────────────────────────────
    generated_fixes = _generate_fixes(
        incident, source_location, source_file_content, crash_line_no, llm, language
    )

    # ── 4. Assemble the single report ─────────────────────────────────────────
    now = datetime.now(UTC).isoformat()
    out: list[str] = [
        f"# 🚨 Incident Report: {incident.title}",
        "",
        "---",
        "",
        "## 📋 Summary",
        "",
        "| Field | Value |",
        "|-------|-------|",
        f"| **Incident ID** | `{incident.id}` |",
        f"| **Service** | `{incident.service}` |",
        f"| **Environment** | `{incident.environment}` |",
        f"| **Generated At** | `{now}` |",
        f"| **Error** | `{incident.error_summary}` |",
        "",
    ]

    # Stack trace block
    if stack_trace.strip():
        out += [
            "## 🔍 Stack Trace",
            "",
            "```",
            stack_trace.strip(),
            "```",
            "",
        ]

    # Exact problem pinpointed to file + line
    if source_location:
        location_header = f"**File:** `{source_location.path}`"
        if crash_line_no:
            location_header += f"  **—  Line:** `{crash_line_no}`"
        out += [
            "## 💥 Exact Problem",
            "",
            location_header,
            "",
            f"> **Root Cause:** {incident.error_summary}",
            "",
        ]
        if source_snippet:
            out += [
                f"```{code_fence}",
                source_snippet,
                "```",
                "",
                "> Lines marked with `>>>` are where execution crashed.",
                "",
            ]

    # All fixes — ranked, with before/after code
    out += [
        "## 🔧 All Possible Fixes",
        "",
        "> Ranked **most recommended → least**. Apply Fix 1 unless you have a specific reason not to.",
        "",
    ]
    for fix in generated_fixes:
        out += [
            f"### Fix {fix['rank']}: {fix['title']}",
            "",
            f"**When to use:** {fix['when']}",
            "",
            "**Before (broken):**",
            f"```{code_fence}",
            fix["before"],
            "```",
            "",
            "**After (fixed):**",
            f"```{code_fence}",
            fix["after"],
            "```",
            "",
            f"**Why this works:** {fix['why']}",
            "",
            "---",
            "",
        ]

    # Code graph affected locations
    if locations:
        out += ["## 🕸️ Code Graph — Affected Locations", ""]
        for loc in locations[:6]:
            out.append(
                f"- `{loc.path}` — confidence `{loc.confidence:.2f}` — _{loc.rationale}_"
            )
        out.append("")

    # Immediate next steps
    out += [
        "## ✅ Immediate Next Steps",
        "",
        "1. Apply **Fix 1** from the section above.",
        f"2. Add a regression test around `{source_location.path if source_location else incident.service}` covering this failure mode.",
        "3. Re-run the deployment or CI pipeline to confirm the service stays healthy.",
        "4. If the issue persists, escalate with the full stack trace to the on-call team.",
        "",
    ]

    report_markdown = "\n".join(out).rstrip() + "\n"
    report_path.write_text(report_markdown, encoding="utf-8")

    return {
        "report_markdown": report_markdown,
        "report_path": str(report_path),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Fix generation helpers
# ─────────────────────────────────────────────────────────────────────────────

def _generate_fixes(
    incident, source_location, source_file_content: str, crash_line_no, llm: OrchestratorLLM, language: str
) -> list[dict]:
    fixes: list[dict] = []

    # LLM fix is always rank 1 when available
    if llm.is_enabled() and source_file_content:
        llm_fix = _llm_fix(llm, incident, source_file_content, crash_line_no, language)
        if llm_fix:
            fixes.append({"rank": 1, **llm_fix})

    # Pattern-based fixes fill the rest
    for i, fix in enumerate(_pattern_fixes(incident.error_summary, source_location, source_file_content, crash_line_no, language), start=len(fixes) + 1):
        fixes.append({"rank": i, **fix})

    return fixes[:5]


def _llm_fix(llm: OrchestratorLLM, incident, source_code: str, crash_line: int | None, language: str) -> dict | None:
    import json, re
    from langchain_core.messages import HumanMessage, SystemMessage

    client = llm._get_client()
    if client is None:
        return None

    language_label = language or "plaintext"

    prompt = (
        f"A {language_label} service crashed with:\n  {incident.error_summary}\n\n"
        f"Stack trace:\n{incident.stack_trace[:800]}\n\n"
        f"Source file:\n```{language_label}\n{source_code[:2000]}\n```\n\n"
        'Return a JSON object with keys: "title", "when", "before", "after", "why". '
        "before/after should be 3-6 line code snippets. JSON only, no markdown."
    )
    try:
        response = client.invoke([
            SystemMessage(content=f"You are a senior {language_label} engineer producing precise fix patches."),
            HumanMessage(content=prompt),
        ])
        text = re.sub(r"```json\s*|```\s*", "", llm._get_content(response)).strip()
        return json.loads(text)
    except Exception:
        return None


def _pattern_fixes(error: str, location, source_code: str, crash_line: int | None, language: str) -> list[dict]:
    import re

    fixes: list[dict] = []
    before_ctx = _extract_crash_context(source_code, crash_line, window=4)
    file_label = location.path if location else "the affected file"
    lower_error = error.lower()

    if language in {"javascript", "typescript"}:
        fixes.append({
            "title": "Guard the boot failure path and log the failing condition explicitly",
            "when": "The service is crashing during startup or immediately after boot with a synthetic or real runtime error.",
            "before": before_ctx or (
                "if (failOnBoot) {\n"
                "  throw new Error('boot failure');\n"
                "}"
            ),
            "after": (
                "if (failOnBoot) {\n"
                "  console.error('[telemetry] boot failure', { failOnBoot });\n"
                "  process.exit(2);\n"
                "}"
            ),
            "why": "Startup failures should be intentional, explicit, and logged with enough context for incident analysis."
        })

        if "not defined" in lower_error or "undefined" in lower_error:
            fixes.append({
                "title": "Validate required values before using them in the failing code path",
                "when": "A variable, config value, or request field may be `undefined` in the crash path.",
                "before": before_ctx or "const value = config.token.trim();",
                "after": (
                    "if (!config?.token) {\n"
                    "  throw new Error('Missing required token');\n"
                    "}\n"
                    "const value = config.token.trim();"
                ),
                "why": "Explicit guards turn ambiguous runtime failures into clear actionable errors and prevent cascading crashes."
            })
        elif "build exploded" in lower_error or "boot failure" in lower_error:
            fixes.append({
                "title": "Gate intentional test crashes behind an environment flag or route",
                "when": "You only want failure injection in controlled test scenarios, not every deployment.",
                "before": before_ctx or "const failOnBoot = true;",
                "after": (
                    "const failOnBoot = process.env.FAIL_MODE === 'true';\n"
                    "if (failOnBoot) {\n"
                    "  process.exit(2);\n"
                    "}"
                ),
                "why": "This keeps telemetry verification available while preventing accidental production crashes."
            })
        return fixes[:5]

    if "nonetype" in lower_error and "attribute" in lower_error:
        attr_m = re.search(r"has no attribute '(.+?)'", error)
        attr = attr_m.group(1) if attr_m else "strip"

        fixes.append({
            "title": f"Guard against `None` before calling `.{attr}()`",
            "when": "The argument can legitimately arrive as `None` — add an early return or raise.",
            "before": before_ctx or (
                f"def validate_credentials(user, password):\n"
                f"    normalized_user = user.{attr}().lower()  # crashes when user is None"
            ),
            "after": (
                f"def validate_credentials(user, password):\n"
                f"    if user is None:\n"
                f"        return False  # or: raise ValueError('user must not be None')\n"
                f"    normalized_user = user.{attr}().lower()"
            ),
            "why": f"`user` is `None` when no account is supplied. Checking first prevents the `AttributeError`.",
        })

        fixes.append({
            "title": "Coerce `None` to empty string with `or`",
            "when": "An empty string is a safe substitute for `None` here (auth will simply fail).",
            "before": before_ctx or f"    normalized_user = user.{attr}().lower()",
            "after": f"    normalized_user = (user or \"\").{attr}().lower()",
            "why": "`(user or \"\")` converts `None` → `\"\"` inline, so `.strip().lower()` never crashes.",
        })

        fixes.append({
            "title": "Validate at the public API boundary (`login_user`)",
            "when": "You want zero invalid inputs ever reaching internal helpers.",
            "before": (
                "def login_user(user, password):\n"
                "    if validate_credentials(user, password):  # user can be None\n"
                "        return 'JWT-TOKEN-123'"
            ),
            "after": (
                "def login_user(user, password):\n"
                "    if not user or not password:\n"
                "        raise ValueError('user and password are required')\n"
                "    if validate_credentials(user, password):\n"
                "        return 'JWT-TOKEN-123'"
            ),
            "why": "Entry-point validation makes the whole module robust — no internal helper ever receives `None`.",
        })
    else:
        fixes.append({
            "title": "Add input validation before the crashing expression",
            "when": "The error can be reproduced with a `None` or unexpected type argument.",
            "before": before_ctx or f"# See {file_label} near line {crash_line}",
            "after": "# Add: if arg is None: raise ValueError(...) or return early",
            "why": "Defensive checks at function boundaries prevent runtime crashes from propagating.",
        })

    return fixes


def _extract_crash_context(source_code: str, crash_line: int | None, window: int = 4) -> str:
    if not source_code or not crash_line:
        return ""
    lines = source_code.splitlines()
    start = max(0, crash_line - window - 1)
    end = min(len(lines), crash_line + window - 1)
    return "\n".join(lines[start:end])


def _detect_language(path: str) -> str:
    suffix = Path(path).suffix.lower()
    return LANGUAGE_BY_EXTENSION.get(suffix, "plaintext")


def _code_fence(language: str) -> str:
    return language if language != "plaintext" else ""
