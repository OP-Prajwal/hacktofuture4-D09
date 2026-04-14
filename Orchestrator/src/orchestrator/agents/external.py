from __future__ import annotations

from orchestrator.connectors import ConnectorRegistry
from orchestrator.state import OrchestratorState


def collect_observability_context(
    state: OrchestratorState,
    registry: ConnectorRegistry,
) -> OrchestratorState:
    incident = state["incident"]
    search_terms = state.get("search_terms", [])
    return {
        "observability_hits": registry.lookup_by_kind("observability", incident, search_terms)
    }


def collect_slack_context(
    state: OrchestratorState,
    registry: ConnectorRegistry,
) -> OrchestratorState:
    incident = state["incident"]
    search_terms = state.get("search_terms", [])
    return {
        "slack_hits": registry.lookup_by_kind("slack", incident, search_terms)
    }


def collect_tracker_context(
    state: OrchestratorState,
    registry: ConnectorRegistry,
) -> OrchestratorState:
    incident = state["incident"]
    search_terms = state.get("search_terms", [])
    return {
        "tracker_hits": registry.lookup_by_kind("tracker", incident, search_terms)
    }


def collect_docs_context(
    state: OrchestratorState,
    registry: ConnectorRegistry,
) -> OrchestratorState:
    incident = state["incident"]
    search_terms = state.get("search_terms", [])
    docs_hits = registry.lookup_by_kind("docs", incident, search_terms)
    memory_hits = registry.lookup_by_kind("memory", incident, search_terms)
    return {"docs_hits": (docs_hits + memory_hits)[:10]}


def merge_external_context(state: OrchestratorState) -> OrchestratorState:
    combined = []
    combined.extend(state.get("observability_hits", []))
    combined.extend(state.get("slack_hits", []))
    combined.extend(state.get("tracker_hits", []))
    combined.extend(state.get("docs_hits", []))
    combined.sort(key=lambda item: item.confidence, reverse=True)
    return {"historical_incidents": combined[:12]}
