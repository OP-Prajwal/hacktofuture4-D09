"""
Auto-Healer Service

When a CI/CD pipeline or production process fails, this service:
1. Constructs an incident payload from the failure logs
2. Invokes the Orchestrator's incident analysis workflow
3. Generates a forensic .md report
4. Stores the report in MongoDB for the Dashboard to display
5. Broadcasts the result to live Dashboard viewers via WebSocket
"""

from __future__ import annotations

import sys
import os
import time
from pathlib import Path
from datetime import datetime, timezone

from db.mongo import mongo


def _json_safe(value):
    """Best-effort conversion for Mongo-storable incident payloads."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    return str(value)


def trigger_incident_analysis(
    workspace: str,
    project: str,
    logs: list[str],
    error_lines: list[str],
    exit_code: int,
    repo_root: str | None = None
) -> dict:
    """
    Trigger the Orchestrator's incident analysis pipeline on a failure.
    Generates a forensic .md report and stores it in MongoDB.
    Returns the diagnosis result with hypotheses, code locations, and the report.
    """
    print(f"\n{'='*60}")
    print(f"[AutoHeal] Failure detected for {workspace}/{project}")
    print("in trigg ",workspace,project)
    if repo_root:
        print(f"[AutoHeal] Repo root: {repo_root}")
    print(f"[AutoHeal] Exit code: {exit_code}")
    print(f"[AutoHeal] Error lines: {len(error_lines)}")
    print(f"{'='*60}\n")

    # Build error summary from stderr lines
    error_summary = "\n".join(error_lines[-10:]) if error_lines else "Process exited with non-zero code"

    # Try to extract a stack trace from the logs
    stack_trace = ""
    in_trace = False
    trace_lines = []
    for line in logs:
        if "Traceback" in line or "Error:" in line or "Exception:" in line:
            in_trace = True
        if in_trace:
            trace_lines.append(line)
    stack_trace = "\n".join(trace_lines[-30:])

    incident_id = f"inc-{workspace[:4]}-{int(time.time()) % 100000:05d}"

    # Try to use the Orchestrator if available
    try:
        # Add the Orchestrator to the path
        orchestrator_path = Path(__file__).resolve().parents[2] / "Orchestrator" / "src"
        if str(orchestrator_path) not in sys.path:
            sys.path.insert(0, str(orchestrator_path))

        from orchestrator.models import IncidentInput
        from orchestrator.llm import LLMSettings, OrchestratorLLM
        from orchestrator.workflow import build_workflow
        from orchestrator.connectors import ConnectorRegistry

        # Build the incident
        incident = IncidentInput(
            id=incident_id,
            title=f"Production Failure: {workspace}/{project}",
            service=project,
            environment="production",
            error_summary=error_summary[:500],
            stack_trace=stack_trace[:2000],
            logs=logs[-30:],
        )

        # Configure LLM from environment
        llm_settings = LLMSettings(
            provider=os.getenv("NEXUS_LLM_PROVIDER", "ollama"),
            model=os.getenv("NEXUS_LLM_MODEL", "qwen2.5-coder:3b"),
            base_url=os.getenv("NEXUS_LLM_BASE_URL", "http://localhost:11434"),
        )
        llm = OrchestratorLLM(llm_settings)

        # Build and run the workflow
        registry = ConnectorRegistry()

        # Use the Nexus-X backend API for localization
        nexus_api_url = os.getenv("NEXUS_API_URL", "http://localhost:8000")
        os.environ["NEXUS_API_URL"] = nexus_api_url

        graph_project = f"{workspace}/{project}"
        resolved_repo_root = Path(repo_root) if repo_root else None
        print(f"[AutoHeal] Orchestrator repo_root={resolved_repo_root}")
        print(f"[AutoHeal] Orchestrator graph_project={graph_project}")
        print(f"[AutoHeal] Orchestrator api_url={nexus_api_url}")

        app = build_workflow(
            connector_registry=registry,
            repo_root=resolved_repo_root,
            graph_project=graph_project,
            llm=llm,
        )

        result = app.invoke({
            "incident": incident,
            "repo_root": resolved_repo_root,
            "graph_project": graph_project,
        })

        # Extract diagnosis
        hypotheses = result.get("hypotheses", [])
        locations = result.get("candidate_locations", [])
        report_markdown = result.get("report_markdown", "")
        report_path = result.get("report_path", "")

        diagnosis = {
            "status": "analyzed",
            "incident_id": incident_id,
            "summary": error_summary[:200],
            "hypotheses": [
                {
                    "title": h.title,
                    "confidence": h.confidence,
                    "evidence": h.evidence,
                    "likely_locations": h.likely_locations,
                    "next_steps": h.next_steps,
                }
                for h in hypotheses[:3]
            ],
            "code_locations": [
                {
                    "path": loc.path,
                    "symbol": loc.symbol,
                    "line_hint": loc.line_hint,
                    "confidence": loc.confidence,
                    "rationale": loc.rationale,
                }
                for loc in locations[:5]
            ],
            "report_markdown": report_markdown,
            "report_path": report_path,
        }

        print(f"[AutoHeal] Analysis complete: {len(hypotheses)} hypotheses, {len(locations)} locations")

    except ImportError as e:
        print(f"[AutoHeal] Orchestrator not available: {e}")
        diagnosis = _fallback_analysis(workspace, project, logs, error_lines, error_summary, incident_id)

    except BaseException as e:
        print(f"[AutoHeal] Analysis failed: {e}")
        import traceback
        traceback.print_exc()
        diagnosis = _fallback_analysis(workspace, project, logs, error_lines, error_summary, incident_id)

    # ── Generate the .md report if not already created ──
    if not diagnosis.get("report_markdown"):
        diagnosis["report_markdown"] = _generate_fallback_report(diagnosis, workspace, project, exit_code, logs)

    # ── Persist report to MongoDB ──
    _store_report(workspace, project, diagnosis, exit_code, logs)

    return diagnosis


def _generate_fallback_report(diagnosis: dict, workspace: str, project: str, exit_code: int, logs: list[str]) -> str:
    """Generate a markdown report when the Orchestrator isn't available."""
    lines = [
        f"# Incident Report: Production Failure in {workspace}/{project}",
        "",
        "## Summary",
        f"- Incident ID: `{diagnosis.get('incident_id', 'unknown')}`",
        f"- Service: `{project}`",
        f"- Environment: `production`",
        f"- Exit Code: `{exit_code}`",
        f"- Generated At: `{datetime.now(timezone.utc).isoformat()}`",
        f"- Error Summary: {diagnosis.get('summary', 'Unknown error')}",
        "",
        "## Likely Code Locations",
    ]

    for loc in diagnosis.get("code_locations", []):
        line_info = f":{loc.get('line_hint', '')}" if loc.get('line_hint') else ""
        lines.append(f"- `{loc.get('path', '?')}{line_info}` confidence `{loc.get('confidence', 0):.2f}`: {loc.get('rationale', '')}")

    if not diagnosis.get("code_locations"):
        lines.append("- No specific locations identified.")

    lines.extend(["", "## Root Cause Hypotheses"])
    for i, h in enumerate(diagnosis.get("hypotheses", []), 1):
        lines.append(f"### {i}. {h.get('title', 'Unknown')}")
        lines.append(f"- Confidence: `{h.get('confidence', 0):.2f}`")
        if h.get("evidence"):
            lines.append("- Evidence:")
            for ev in h["evidence"]:
                lines.append(f"  - {ev}")
        if h.get("next_steps"):
            lines.append("- Recommended Next Steps:")
            for step in h["next_steps"]:
                lines.append(f"  - {step}")
        lines.append("")

    lines.extend(["", "## Recent Logs (last 20 lines)"])
    lines.append("```")
    for log_line in logs[-20:]:
        lines.append(log_line)
    lines.append("```")

    return "\n".join(lines) + "\n"


def _store_report(workspace: str, project: str, diagnosis: dict, exit_code: int, logs: list[str]):
    """Persist the incident report to MongoDB for Dashboard access."""
    payload = {
        "workspace": workspace,
        "project": project,
        "incident_id": diagnosis.get("incident_id"),
        "status": diagnosis.get("status"),
        "summary": diagnosis.get("summary"),
        "exit_code": exit_code,
        "hypotheses": _json_safe(diagnosis.get("hypotheses", [])),
        "code_locations": _json_safe(diagnosis.get("code_locations", [])),
        "report_markdown": diagnosis.get("report_markdown", ""),
        "log_lines": len(logs),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        reports_col = mongo.get_collection("incident_reports")
        reports_col.insert_one(payload)
        print(f"[AutoHeal] Report stored in MongoDB: incident_reports/{diagnosis.get('incident_id')}")
    except Exception as e:
        print(f"[AutoHeal] Failed to store incident report: {e}")


def _fallback_analysis(
    workspace: str,
    project: str,
    logs: list[str],
    error_lines: list[str],
    error_summary: str,
    incident_id: str,
) -> dict:
    """
    Basic fallback analysis when the Orchestrator is not available.
    Extracts file hints and error patterns from the raw logs.
    """
    import re

    # Extract file:line patterns from error output
    file_hints = []
    for line in error_lines + logs[-20:]:
        matches = re.findall(
            r'([A-Za-z0-9_\-/]+\.(?:py|ts|tsx|js|jsx|go|java|rb)):(\d+)',
            line
        )
        for file_path, line_num in matches:
            file_hints.append({
                "path": file_path,
                "line_hint": int(line_num),
                "confidence": 0.6,
                "rationale": "Extracted from error output"
            })

    return {
        "status": "fallback",
        "incident_id": incident_id,
        "summary": error_summary[:200],
        "hypotheses": [
            {
                "title": "Process failure — automated analysis with code graph",
                "confidence": 0.3,
                "evidence": error_lines[-5:] if error_lines else ["No stderr captured"],
                "likely_locations": [h["path"] for h in file_hints[:3]],
                "next_steps": [
                    "Check the error output above for specific failure details",
                    "Review recent code changes in the affected files",
                    "Install the Orchestrator package for deeper AI analysis"
                ]
            }
        ],
        "code_locations": file_hints[:5],
        "report_markdown": None,
        "report_path": None,
    }
