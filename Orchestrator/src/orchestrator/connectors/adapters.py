from __future__ import annotations

from orchestrator.models import HistoricalIncident, IncidentInput

from .base import ExternalKnowledgeConnector
from .mcp import MCPClient, MCPQuery


class MCPBackedConnector(ExternalKnowledgeConnector):
    def __init__(self, client: MCPClient):
        self.client = client

    def lookup(self, incident: IncidentInput, search_terms: list[str]) -> list[HistoricalIncident]:
        records = self.client.search(
            MCPQuery(
                terms=search_terms,
                service=incident.service,
                environment=incident.environment,
                incident_id=incident.id,
            )
        )
        return [
            HistoricalIncident(
                title=record.title,
                source=f"{self.name}:{self.client.name}",
                connector_kind=self.kind,
                summary=record.summary,
                resolution=record.resolution,
                confidence=record.confidence,
                link=record.link,
            )
            for record in records
        ]


class SlackMCPConnector(MCPBackedConnector):
    name = "slack"
    kind = "slack"


class IncidentTrackerMCPConnector(MCPBackedConnector):
    name = "incident_tracker"
    kind = "tracker"


class DocsRunbookMCPConnector(MCPBackedConnector):
    name = "docs_runbook"
    kind = "docs"


class ObservabilityMCPConnector(MCPBackedConnector):
    name = "observability"
    kind = "observability"
