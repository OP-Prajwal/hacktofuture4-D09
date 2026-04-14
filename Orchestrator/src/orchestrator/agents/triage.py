from __future__ import annotations

import re

from orchestrator.agents.roles import get_default_agent_roles
from orchestrator.models import EvidenceItem
from orchestrator.state import OrchestratorState


def triage_incident(state: OrchestratorState) -> OrchestratorState:
    incident = state["incident"]
    search_terms = _extract_search_terms(
        incident.error_summary,
        incident.stack_trace,
        " ".join(incident.logs[:20]),
        incident.service,
    )
    evidence = list(state.get("evidence", []))
    evidence.append(
        EvidenceItem(
            source="triage",
            kind="summary",
            content=incident.error_summary,
            trust=0.95,
        )
    )
    if incident.stack_trace:
        evidence.append(
            EvidenceItem(
                source="triage",
                kind="stack_trace",
                content=incident.stack_trace[:2000],
                trust=0.98,
            )
        )

    return {
        "agent_roles": get_default_agent_roles(),
        "search_terms": search_terms,
        "evidence": evidence,
    }


def _extract_search_terms(*texts: str) -> list[str]:
    tokens: list[str] = []
    for text in texts:
        tokens.extend(re.findall(r"[A-Za-z_][A-Za-z0-9_\-/.:]{2,}", text))

    normalized: list[str] = []
    seen = set()
    for token in tokens:
        cleaned = token.strip(".,:;()[]{}<>").lower()
        if len(cleaned) < 3:
            continue
        if cleaned in seen:
            continue
        seen.add(cleaned)
        normalized.append(cleaned)
    return normalized[:25]
