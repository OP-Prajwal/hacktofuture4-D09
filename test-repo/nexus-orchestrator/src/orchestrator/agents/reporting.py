from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from orchestrator.llm import OrchestratorLLM
from orchestrator.state import OrchestratorState


def write_report(state: OrchestratorState, output_dir: Path, llm: OrchestratorLLM) -> OrchestratorState:
    incident = state["incident"]
    evidence = state.get("evidence", [])
    historical = state.get("historical_incidents", [])
    locations = state.get("candidate_locations", [])
    hypotheses = state.get("hypotheses", [])
    roles = state.get("agent_roles", [])

    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"{incident.id}.md"

    summary = llm.summarize_incident(incident)

    lines: list[str] = [
        f"# Incident Report: {incident.title}",
        "",
        "## Summary",
        f"- Incident ID: `{incident.id}`",
        f"- Service: `{incident.service}`",
        f"- Environment: `{incident.environment}`",
        f"- Generated At: `{datetime.now(UTC).isoformat()}`",
        f"- Overview: {summary}",
        f"- Error Summary: {incident.error_summary}",
        "",
        "## Agent Roles",
    ]

    if roles:
        for role in roles:
            lines.append(
                f"- `{role.name}`: {role.responsibility} Tools: {', '.join(role.tool_domains)}"
            )
    else:
        lines.append("- No agent role metadata attached.")

    lines.extend([
        "",
        "## Extracted Evidence",
    ])

    if evidence:
        for item in evidence:
            lines.append(f"- `{item.kind}` from `{item.source}` (trust `{item.trust:.2f}`): {item.content}")
    else:
        lines.append("- No structured evidence extracted.")

    lines.extend(["", "## Likely Code Locations"])
    if locations:
        for location in locations:
            line_info = f":{location.line_hint}" if location.line_hint else ""
            lines.append(
                f"- `{location.path}{line_info}` confidence `{location.confidence:.2f}`: {location.rationale}"
            )
    else:
        lines.append("- No likely code locations found.")

    lines.extend(["", "## Similar Historical Incidents"])
    if historical:
        for item in historical:
            resolution = f" Resolution: {item.resolution}" if item.resolution else ""
            link = f" Link: `{item.link}`" if item.link else ""
            lines.append(
                f"- `{item.title}` from `{item.source}` kind `{item.connector_kind}` confidence `{item.confidence:.2f}`. {item.summary}{resolution}{link}"
            )
    else:
        lines.append("- No similar incidents found in configured connectors.")

    lines.extend(["", "## Ranked Root Cause Hypotheses"])
    for index, hypothesis in enumerate(hypotheses, start=1):
        lines.append(f"### {index}. {hypothesis.title}")
        lines.append(f"- Confidence: `{hypothesis.confidence:.2f}`")
        if hypothesis.evidence:
            lines.append("- Evidence:")
            for item in hypothesis.evidence:
                lines.append(f"  - {item}")
        if hypothesis.likely_locations:
            lines.append("- Likely Locations:")
            for item in hypothesis.likely_locations:
                lines.append(f"  - `{item}`")
        if hypothesis.next_steps:
            lines.append("- Recommended Next Steps:")
            for item in hypothesis.next_steps:
                lines.append(f"  - {item}")
        lines.append("")

    report_markdown = "\n".join(lines).rstrip() + "\n"
    report_path.write_text(report_markdown, encoding="utf-8")

    return {
        "report_markdown": report_markdown,
        "report_path": str(report_path),
    }
