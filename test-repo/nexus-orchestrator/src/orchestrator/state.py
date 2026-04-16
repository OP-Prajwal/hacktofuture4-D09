from __future__ import annotations

from typing import TypedDict

from .models import CodeLocation, EvidenceItem, HistoricalIncident, Hypothesis, IncidentInput


class OrchestratorState(TypedDict, total=False):
    incident: IncidentInput
    agent_roles: list
    search_terms: list[str]
    evidence: list[EvidenceItem]
    observability_hits: list[HistoricalIncident]
    slack_hits: list[HistoricalIncident]
    tracker_hits: list[HistoricalIncident]
    docs_hits: list[HistoricalIncident]
    historical_incidents: list[HistoricalIncident]
    candidate_locations: list[CodeLocation]
    hypotheses: list[Hypothesis]
    report_markdown: str
    report_path: str
