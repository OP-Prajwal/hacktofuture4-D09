from __future__ import annotations

from pathlib import Path
from pydantic import BaseModel, Field


class IncidentInput(BaseModel):
    id: str
    title: str
    service: str
    environment: str
    error_summary: str
    stack_trace: str = ""
    logs: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class EvidenceItem(BaseModel):
    source: str
    kind: str
    content: str
    trust: float = 0.5


class AgentRole(BaseModel):
    name: str
    responsibility: str
    tool_domains: list[str] = Field(default_factory=list)


class CodeLocation(BaseModel):
    path: str
    symbol: str | None = None
    line_hint: int | None = None
    confidence: float = 0.0
    rationale: str


class HistoricalIncident(BaseModel):
    title: str
    source: str
    connector_kind: str = "unknown"
    summary: str
    resolution: str | None = None
    confidence: float = 0.0
    link: str | None = None


class Hypothesis(BaseModel):
    title: str
    confidence: float
    evidence: list[str] = Field(default_factory=list)
    likely_locations: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)


class ReportArtifact(BaseModel):
    markdown_path: Path
