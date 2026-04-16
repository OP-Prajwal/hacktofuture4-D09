import json
from pathlib import Path
from typing import Any

from orchestrator.models import HistoricalIncident, IncidentInput

from .adapters import (
    DocsRunbookMCPConnector,
    IncidentTrackerMCPConnector,
    ObservabilityMCPConnector,
    SlackMCPConnector,
)
from .base import ExternalKnowledgeConnector
from .mcp import StdioMCPClient


class ConnectorRegistry:
    def __init__(self, connectors: list[ExternalKnowledgeConnector] | None = None):
        self._connectors = connectors or []

    def add(self, connector: ExternalKnowledgeConnector) -> None:
        self._connectors.append(connector)

    def load_mcp_config(self, config_path: Path) -> None:
        """
        Load MCP server configurations from a JSON file.
        Example format:
        {
          "slack": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-slack"]},
          "observability": {"command": "python", "args": ["-m", "my_obs_mcp_server"]}
        }
        """
        if not config_path.exists():
            return

        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
            mapping = {
                "slack": SlackMCPConnector,
                "tracker": IncidentTrackerMCPConnector,
                "docs": DocsRunbookMCPConnector,
                "observability": ObservabilityMCPConnector,
            }

            for kind, server_cfg in config.items():
                if kind in mapping:
                    client = StdioMCPClient(
                        name=kind,
                        command=server_cfg["command"],
                        args=server_cfg.get("args", []),
                        env=server_cfg.get("env"),
                    )
                    self.add(mapping[kind](client))
        except Exception as e:
            print(f"Failed to load MCP config: {e}")

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
