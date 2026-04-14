from __future__ import annotations

from orchestrator.models import HistoricalIncident, IncidentInput

from .base import ExternalKnowledgeConnector


class ConnectorRegistry:
    def __init__(self, connectors: list[ExternalKnowledgeConnector] | None = None):
        self._connectors = connectors or []

    def add(self, connector: ExternalKnowledgeConnector) -> None:
        self._connectors.append(connector)

    def lookup_by_kind(
        self,
        kind: str,
        incident: IncidentInput,
        search_terms: list[str],
    ) -> list[HistoricalIncident]:
        aggregated: list[HistoricalIncident] = []
        for connector in self._connectors:
            if getattr(connector, "kind", None) != kind:
                continue
            aggregated.extend(connector.lookup(incident, search_terms))
        aggregated.sort(key=lambda item: item.confidence, reverse=True)
        return aggregated[:10]

    def lookup(self, incident: IncidentInput, search_terms: list[str]) -> list[HistoricalIncident]:
        aggregated: list[HistoricalIncident] = []
        for connector in self._connectors:
            aggregated.extend(connector.lookup(incident, search_terms))
        aggregated.sort(key=lambda item: item.confidence, reverse=True)
        return aggregated[:10]
