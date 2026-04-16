from __future__ import annotations

from abc import ABC, abstractmethod

from orchestrator.models import HistoricalIncident, IncidentInput


class ExternalKnowledgeConnector(ABC):
    name: str = "connector"
    kind: str = "generic"

    @abstractmethod
    def lookup(self, incident: IncidentInput, search_terms: list[str]) -> list[HistoricalIncident]:
        """Return potentially similar historical incidents or runbook hits."""
