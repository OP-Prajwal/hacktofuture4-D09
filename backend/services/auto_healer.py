"""
Auto-Healer Service

When a CI/CD pipeline fails, this service:
1. Constructs an incident payload from the failure logs
2. Invokes the Orchestrator's incident analysis workflow
3. Returns ranked root-cause hypotheses and recommended fixes
"""

from __future__ import annotations

import sys
import os
import time
from pathlib import Path


def trigger_auto_heal(
    workspace: str,
    project: str,
    logs: list[str],
    error_lines: list[str],
    exit_code: int,
    repo_root: str | None = None
) -> dict:
    """
    Trigger the Orchestrator's incident analysis pipeline on a CI failure.
    Returns the diagnosis result with hypotheses and code locations.
    """
    print(f"\n{'='*60}")
    print(f"[AutoHeal] CI failure detected for {workspace}/{project}")
    if repo_root:
        print(f"[AutoHeal] Repo root: {repo_root}")
    print(f"[AutoHeal] Exit code: {exit_code}")
    print(f"[AutoHeal] Error lines: {len(error_lines)}")
    print(f"{'='*60}\n")

    # Build error summary from stderr lines
    error_summary = "\n".join(error_lines[-10:]) if error_lines else "CI pipeline exited with non-zero code"

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

    # Try to use the Orchestrator if available
    try:
        # Add the Orchestrator to the path
        orchestrator_path = Path(__file__).resolve().parents[2] / ".." / "Orchestrator" / "src"
        if str(orchestrator_path) not in sys.path:
            sys.path.insert(0, str(orchestrator_path))

        from orchestrator.models import IncidentInput
        from orchestrator.llm import LLMSettings, OrchestratorLLM
        from orchestrator.workflow import build_workflow
        from orchestrator.connectors import ConnectorRegistry

        # Build the incident
        incident = IncidentInput(
            id=f"ci-{workspace}-{project}-{int(time.time())}",
            title=f"CI Build Failed: {workspace}/{project}",
            service=project,
            environment="ci",
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
        app = build_workflow(
            connector_registry=registry,
            repo_root=Path(repo_root) if repo_root else None,
            llm=llm,
        )

        result = app.invoke({"incident": incident})

        # Extract diagnosis
        hypotheses = result.get("hypotheses", [])
        locations = result.get("candidate_locations", [])

        diagnosis = {
            "status": "analyzed",
            "incident_id": incident.id,
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
            "report_path": result.get("report_path"),
        }

        print(f"[AutoHeal] Analysis complete: {len(hypotheses)} hypotheses, {len(locations)} locations")
        return diagnosis

    except ImportError as e:
        print(f"[AutoHeal] Orchestrator not available: {e}")
        # Fallback: basic analysis without the orchestrator
        return _fallback_analysis(workspace, project, logs, error_lines, error_summary)

    except Exception as e:
        print(f"[AutoHeal] Analysis failed: {e}")
        return _fallback_analysis(workspace, project, logs, error_lines, error_summary)


def _fallback_analysis(
    workspace: str,
    project: str,
    logs: list[str],
    error_lines: list[str],
    error_summary: str
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
        "incident_id": f"ci-{workspace}-{project}-{int(time.time())}",
        "summary": error_summary[:200],
        "hypotheses": [
            {
                "title": "CI pipeline failure — manual investigation needed",
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
        "report_path": None,
    }
