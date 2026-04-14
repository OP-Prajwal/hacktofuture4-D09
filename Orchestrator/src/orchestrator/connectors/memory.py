from __future__ import annotations

import json
from pathlib import Path

from orchestrator.models import HistoricalIncident, IncidentInput


class StaticIncidentMemoryConnector:
    name = "incident_memory"
    kind = "memory"

    def __init__(self, memory_dir: Path):
        self.memory_dir = memory_dir

    def lookup(self, incident: IncidentInput, search_terms: list[str]) -> list[HistoricalIncident]:
        if not self.memory_dir.exists():
            return []

        hits: list[HistoricalIncident] = []
        for path in self.memory_dir.rglob("*"):
            if path.suffix.lower() == ".json":
                record = self._read_json_record(path)
                if record and self._score_text(record.title + " " + record.summary, search_terms) > 0:
                    hits.append(record)
            elif path.suffix.lower() == ".md":
                record = self._read_markdown_record(path)
                if record and self._score_text(record.title + " " + record.summary, search_terms) > 0:
                    hits.append(record)

        hits.sort(key=lambda item: item.confidence, reverse=True)
        return hits[:5]

    def _read_json_record(self, path: Path) -> HistoricalIncident | None:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

        title = str(data.get("title") or path.stem)
        summary = str(data.get("summary") or "")
        resolution = data.get("resolution")
        confidence = float(data.get("confidence") or 0.5)
        return HistoricalIncident(
            title=title,
            source=f"{self.name}:{path.name}",
            connector_kind=self.kind,
            summary=summary,
            resolution=resolution,
            confidence=confidence,
            link=str(path),
        )

    def _read_markdown_record(self, path: Path) -> HistoricalIncident | None:
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            return None

        title = path.stem
        for line in text.splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
                break

        confidence = min(0.95, 0.35 + 0.05 * len(text.splitlines()))
        summary = text[:600].strip()
        return HistoricalIncident(
            title=title,
            source=f"{self.name}:{path.name}",
            connector_kind=self.kind,
            summary=summary,
            resolution=None,
            confidence=confidence,
            link=str(path),
        )

    def _score_text(self, text: str, search_terms: list[str]) -> int:
        lowered = text.lower()
        return sum(1 for term in search_terms if term and term.lower() in lowered)
