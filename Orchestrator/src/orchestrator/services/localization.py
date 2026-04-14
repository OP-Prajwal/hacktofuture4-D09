from __future__ import annotations

import os
import re
from pathlib import Path

from dotenv import load_dotenv

from orchestrator.models import CodeLocation, IncidentInput

try:
    from neo4j import GraphDatabase
except ImportError:  # pragma: no cover - optional dependency at runtime until installed
    GraphDatabase = None


load_dotenv(Path(__file__).resolve().parents[3] / ".env")

GRAPH_NODE_LABELS = ("Function", "Class", "File", "Module")
GRAPH_RELATIONSHIP_TYPES = ("CALLS", "IMPORTS", "EXTENDS", "CONTAINS", "BELONGS_TO", "DEPENDS_ON")


class Neo4jGraphLocator:
    def __init__(self, project: str | None = None):
        self.project = project or os.getenv("NEO4J_PROJECT") or os.getenv("NEXUS_GRAPH_PROJECT")
        self.uri = os.getenv("NEO4J_URI")
        self.username = os.getenv("NEO4J_USERNAME")
        self.password = os.getenv("NEO4J_PASSWORD")
        self.database = os.getenv("NEO4J_DATABASE")

    def is_configured(self) -> bool:
        return bool(
            GraphDatabase is not None
            and self.uri
            and self.username
            and self.password
            and self.database
            and self.project
        )

    def locate(self, incident: IncidentInput, search_terms: list[str]) -> list[CodeLocation]:
        if not self.is_configured():
            return []

        file_hints = self._extract_file_hints(incident.stack_trace)
        symbol_hints = self._extract_symbol_hints(incident, search_terms)
        normalized_terms = [term.lower() for term in search_terms if len(term) >= 3][:25]

        query = """
        MATCH (target {project: $project})
        WHERE any(label IN labels(target) WHERE label IN $node_labels)
          AND (
            target.name IN $symbol_hints
            OR target.file_path IN $file_hints
            OR any(hint IN $file_hints WHERE target.file_path ENDS WITH hint)
            OR any(term IN $search_terms WHERE toLower(coalesce(target.qualified_name, "")) CONTAINS term)
            OR any(term IN $search_terms WHERE toLower(coalesce(target.file_path, "")) CONTAINS term)
            OR any(term IN $search_terms WHERE toLower(coalesce(target.summary, "")) CONTAINS term)
          )
        OPTIONAL MATCH (target)-[r]->(downstream {project: $project})
        WHERE type(r) IN $relationship_types
        RETURN labels(target) AS labels,
               target.name AS name,
               target.qualified_name AS qualified_name,
               target.file_path AS file_path,
               target.start_line AS start_line,
               target.summary AS summary,
               target.blast_radius AS blast_radius,
               collect(DISTINCT {
                   rel_type: type(r),
                   neighbor: coalesce(downstream.name, downstream.file_path, downstream.qualified_name)
               })[..8] AS outbound
        ORDER BY coalesce(target.blast_radius, 0) DESC, target.name ASC
        LIMIT 12
        """

        try:
            with GraphDatabase.driver(self.uri, auth=(self.username, self.password)) as driver:
                with driver.session(database=self.database) as session:
                    records = session.run(
                        query,
                        {
                            "project": self.project,
                            "node_labels": list(GRAPH_NODE_LABELS),
                            "relationship_types": list(GRAPH_RELATIONSHIP_TYPES),
                            "search_terms": normalized_terms,
                            "file_hints": file_hints,
                            "symbol_hints": symbol_hints,
                        },
                    )
                    rows = [record.data() for record in records]
        except Exception:
            return []

        return [self._to_code_location(row, file_hints, normalized_terms) for row in rows if row.get("file_path")]

    def _extract_symbol_hints(self, incident: IncidentInput, search_terms: list[str]) -> list[str]:
        symbols = set()
        stack_hints = re.findall(r"(?:at|in)\s+([A-Za-z_][A-Za-z0-9_]*)", incident.stack_trace)
        for hint in stack_hints:
            if len(hint) >= 3:
                symbols.add(hint)

        for term in search_terms:
            candidate = term.split("::")[-1].split(".")[-1].split("/")[-1]
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", candidate):
                symbols.add(candidate)

        return sorted(symbols)[:25]

    def _to_code_location(self, row: dict, file_hints: list[str], search_terms: list[str]) -> CodeLocation:
        file_path = row["file_path"]
        blast_radius = row.get("blast_radius") or 0
        summary = row.get("summary") or ""
        name = row.get("name")
        outbound = row.get("outbound") or []

        score = 0.35
        rationale_bits: list[str] = ["matched Neo4j project-scoped code graph"]

        if any(file_path.endswith(hint) for hint in file_hints):
            score += 0.25
            rationale_bits.append("matched stack trace file hint")
        if name and any(term == name.lower() for term in search_terms):
            score += 0.15
            rationale_bits.append("matched extracted symbol")
        if summary and any(term in summary.lower() for term in search_terms):
            score += 0.1
            rationale_bits.append("summary overlaps incident terms")
        if blast_radius:
            score += min(blast_radius / 100.0, 0.1)
            rationale_bits.append(f"blast radius {blast_radius}")
        if outbound:
            rationale_bits.append(f"{len(outbound)} immediate graph links")

        return CodeLocation(
            path=file_path,
            symbol=row.get("qualified_name") or name,
            line_hint=row.get("start_line"),
            confidence=min(score, 0.98),
            rationale=", ".join(rationale_bits),
        )

    def _extract_file_hints(self, stack_trace: str) -> list[str]:
        hints = set()
        for match in re.finditer(
            r"([A-Za-z0-9_\-/]+\.(?:py|ts|tsx|js|jsx|go|java|rb|php|rs|cs))(?::(\d+))?",
            stack_trace,
        ):
            hints.add(match.group(1).replace("\\", "/"))
        return sorted(hints)


class RepositoryLocator:
    def __init__(self, repo_root: Path | None = None, graph_project: str | None = None):
        self.repo_root = repo_root
        self.graph_locator = Neo4jGraphLocator(project=graph_project)

    def locate(self, incident: IncidentInput, search_terms: list[str]) -> list[CodeLocation]:
        graph_hits = self.graph_locator.locate(incident, search_terms)
        repo_hits = self._locate_in_repo(incident, search_terms)
        return self._merge_locations(graph_hits, repo_hits)

    def _locate_in_repo(self, incident: IncidentInput, search_terms: list[str]) -> list[CodeLocation]:
        if self.repo_root is None or not self.repo_root.exists():
            return []

        candidate_files: list[CodeLocation] = []
        file_hints = self._extract_file_hints(incident.stack_trace)
        lowered_terms = [term.lower() for term in search_terms if len(term) >= 3]

        for path in self.repo_root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".lock"}:
                continue

            score = 0.0
            rationale_bits: list[str] = []
            rel = path.relative_to(self.repo_root).as_posix()

            if any(rel.endswith(file_hint) for file_hint in file_hints):
                score += 0.6
                rationale_bits.append("matched stack trace file hint")

            try:
                text = path.read_text(encoding="utf-8")
            except Exception:
                continue

            lowered_text = text.lower()
            for term in lowered_terms:
                if term in lowered_text:
                    score += 0.08
            if incident.service.lower() in rel.lower():
                score += 0.15
                rationale_bits.append("path overlaps service name")

            if score <= 0:
                continue

            line_hint = self._find_line_hint(text, lowered_terms)
            candidate_files.append(
                CodeLocation(
                    path=rel,
                    line_hint=line_hint,
                    confidence=min(score, 0.95),
                    rationale=", ".join(rationale_bits) or "matched incident search terms",
                )
            )

        candidate_files.sort(key=lambda item: item.confidence, reverse=True)
        return candidate_files[:8]

    def _merge_locations(
        self,
        graph_hits: list[CodeLocation],
        repo_hits: list[CodeLocation],
    ) -> list[CodeLocation]:
        merged: dict[tuple[str, str | None], CodeLocation] = {}
        for location in graph_hits + repo_hits:
            key = (location.path, location.symbol)
            existing = merged.get(key)
            if existing is None or location.confidence > existing.confidence:
                merged[key] = location
        ordered = sorted(merged.values(), key=lambda item: item.confidence, reverse=True)
        return ordered[:8]

    def _extract_file_hints(self, stack_trace: str) -> list[str]:
        hints = set()
        for match in re.finditer(
            r"([A-Za-z0-9_\-/]+\.(?:py|ts|tsx|js|jsx|go|java|rb|php|rs|cs))(?::(\d+))?",
            stack_trace,
        ):
            hints.add(match.group(1).replace("\\", "/"))
        return sorted(hints)

    def _find_line_hint(self, text: str, search_terms: list[str]) -> int | None:
        lines = text.splitlines()
        for index, line in enumerate(lines, start=1):
            lowered = line.lower()
            if any(term in lowered for term in search_terms):
                return index
        return None
