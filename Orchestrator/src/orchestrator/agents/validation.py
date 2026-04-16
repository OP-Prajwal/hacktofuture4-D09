from __future__ import annotations

from orchestrator.llm import OrchestratorLLM
from orchestrator.services import RepositoryLocator
from orchestrator.state import OrchestratorState


def localize_code(state: OrchestratorState, locator: RepositoryLocator) -> OrchestratorState:
    incident = state["incident"]
    search_terms = state.get("search_terms", [])
    candidate_locations = locator.locate(incident, search_terms)
    # also expose under 'locations' so the reporter can find it without aliasing
    return {"candidate_locations": candidate_locations, "locations": candidate_locations}


def rank_hypotheses(state: OrchestratorState, llm: OrchestratorLLM) -> OrchestratorState:
    incident = state["incident"]
    historical = state.get("historical_incidents", [])
    locations = state.get("candidate_locations", [])
    hypotheses = llm.generate_hypotheses(incident, locations, historical)
    return {"hypotheses": hypotheses}
