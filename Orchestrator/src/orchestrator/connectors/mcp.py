import json
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


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


class MockMCPClient(MCPClient):
    """A mock client for testing that returns no results."""

    def __init__(self, name: str = "mock"):
        self.name = name

    def search(self, query: MCPQuery) -> list[MCPRecord]:
        return []


class StdioMCPClient(MCPClient):
    """
    A real MCP client that talks to an MCP server over stdio.
    This uses the 'mcp' SDK to call a 'search_incidents' or similar tool.
    """

    def __init__(self, name: str, command: str, args: list[str] | None = None, env: dict[str, str] | None = None):
        self.name = name
        self.command = command
        self.args = args or []
        self.env = env

    def search(self, query: MCPQuery) -> list[MCPRecord]:
        """
        In a real implementation, this would use the mcp python SDK's ClientSession.
        For now, we implement a lightweight subprocess-based call to a tool if the server
        supports a simple 'run-tool' style CLI, or we use the SDK if available.
        """
        try:
            # We try to use the MCP SDK if it's installed and working.
            # If not, we log and return empty to avoid crashing the pipeline.
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
            import asyncio

            async def _run_search():
                params = StdioServerParameters(
                    command=self.command,
                    args=self.args,
                    env=self.env,
                )
                async with stdio_client(params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        
                        # We assume the MCP server has a 'search' tool.
                        # This matches the 'v1 external MCP priorities' in README.
                        result = await session.call_tool(
                            "search",
                            arguments={
                                "queries": query.terms,
                                "service": query.service,
                                "limit": query.limit,
                            }
                        )
                        
                        # Parse the tool result (usually a list of content items)
                        records: list[MCPRecord] = []
                        if hasattr(result, 'content') and isinstance(result.content, list):
                            for item in result.content:
                                if hasattr(item, 'text'):
                                    try:
                                        data = json.loads(item.text)
                                        if isinstance(data, list):
                                            for r in data:
                                                records.append(MCPRecord(**r))
                                        elif isinstance(data, dict):
                                            records.append(MCPRecord(**data))
                                    except Exception:
                                        # Fallback to raw text if not JSON
                                        records.append(MCPRecord(
                                            title=f"Result from {self.name}",
                                            summary=item.text[:500],
                                            confidence=0.4
                                        ))
                        return records

            # Since the orchestrator workflow is currently synchronous (LangGraph default),
            # we run the async client in a new event loop.
            return asyncio.run(_run_search())

        except Exception as e:
            # If MCP is not available or fails, we return an empty list but could log the error.
            # In a production environment, we'd use a proper logger.
            print(f"MCP Client {self.name} failed: {e}")
            return []
