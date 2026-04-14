from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class MCPQuery:
    terms: list[str]
    service: str
    environment: str
    incident_id: str
    limit: int = 5


@dataclass
class MCPRecord:
    title: str
    summary: str
    link: str | None = None
    resolution: str | None = None
    confidence: float = 0.5
    metadata: dict[str, str] = field(default_factory=dict)


class MCPClient(ABC):
    name: str = "mcp"

    @abstractmethod
    def search(self, query: MCPQuery) -> list[MCPRecord]:
        """Query an external MCP-integrated system for incident-relevant records."""
