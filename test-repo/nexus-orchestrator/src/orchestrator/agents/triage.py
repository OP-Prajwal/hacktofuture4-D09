from __future__ import annotations

from orchestrator.agents.roles import get_default_agent_roles
from orchestrator.llm import OrchestratorLLM
from orchestrator.models import EvidenceItem
from orchestrator.state import OrchestratorState


def triage_incident(state: OrchestratorState, llm: OrchestratorLLM) -> OrchestratorState:
    incident = state["incident"]
    search_terms = llm.extract_search_terms(incident)
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
