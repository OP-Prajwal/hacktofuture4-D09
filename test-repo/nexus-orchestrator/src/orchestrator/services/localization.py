from __future__ import annotations

import os
import re
import requests
from pathlib import Path

from dotenv import load_dotenv

from orchestrator.models import CodeLocation, IncidentInput

load_dotenv(Path(__file__).resolve().parents[3] / ".env")

class NexusGraphLocator:
    def __init__(self, project: str | None = None):
        self.project = project or os.getenv("NEO4J_PROJECT") or os.getenv("NEXUS_GRAPH_PROJECT")
        
        # Try to use configured API URL, default to localhost
        api_base = os.getenv("NEXUS_API_URL")
        # Strip trailing slash if present
        if api_base and api_base.endswith('/'):
            api_base = api_base[:-1]
        self.api_url = api_base or "http://localhost:8000"

    def is_configured(self) -> bool:
        return bool(self.project and self.api_url)

    def locate(self, incident: IncidentInput, search_terms: list[str]) -> list[CodeLocation]:
        if not self.is_configured():
            return []

        file_hints = self._extract_file_hints(incident.stack_trace)
        symbol_hints = self._extract_symbol_hints(incident, search_terms)
        normalized_terms = [term.lower() for term in search_terms if len(term) >= 3][:25]

        # Extract workspace and project
        parts = self.project.split('/')
        if len(parts) >= 2:
            workspace, project_name = parts[0], parts[1]
        else:
            return []

        endpoint = f"{self.api_url}/api/repo/{workspace}/{project_name}/locate"
        
        try:
            res = requests.post(
                endpoint,
                json={
                    "search_terms": normalized_terms,
                    "file_hints": file_hints,
                    "symbol_hints": symbol_hints,
                },
                timeout=30.0
            )
            
            if res.status_code != 200:
                print(f"[Orchestrator] Backend locator failed: {res.text}")
                return []
                
            rows = res.json()
        except Exception as e:
            print(f"[Orchestrator] Failed to connect to backend locator: {e}")
            return []

        return [self._to_code_location(row, file_hints, normalized_terms) for row in rows if row.get("file_path")]

    def describe_project(self) -> dict:
        details = {
            "configured": self.is_configured(),
            "uri": self.api_url,
            "database": "nexus-backend",
            "project": self.project,
            "counts": {},
        }
        # A mock implementation or future backend call if needed
        return details

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
        rationale_bits: list[str] = ["matched Nexus project-scoped code graph"]

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
        resolved_project = graph_project or self._resolve_graph_project(repo_root)
        self.graph_locator = NexusGraphLocator(project=resolved_project)

    def locate(self, incident: IncidentInput, search_terms: list[str]) -> list[CodeLocation]:
        graph_hits = self.graph_locator.locate(incident, search_terms)
        repo_hits = self._locate_in_repo(incident, search_terms)
        return self._merge_locations(graph_hits, repo_hits)

    def describe(self) -> dict:
        repo_root = str(self.repo_root) if self.repo_root else None
        repo_exists = bool(self.repo_root and self.repo_root.exists())
        return {
            "repo_root": repo_root,
            "repo_root_exists": repo_exists,
            "graph": self.graph_locator.describe_project(),
        }

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

    def _resolve_graph_project(self, repo_root: Path | None) -> str | None:
        candidates: list[Path] = []
        if repo_root is not None:
            candidates.append(repo_root)
        candidates.append(Path.cwd())

        seen: set[Path] = set()
        for base in candidates:
            if base in seen:
                continue
            seen.add(base)
            remote = self._read_remote_from_nexus_config(base)
            if remote:
                return remote
        return None

    def _read_remote_from_nexus_config(self, base: Path) -> str | None:
        config_path = base / ".nexus" / "config.json"
        if not config_path.exists():
            return None
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
        except Exception:
            return None
        remote = data.get("remote")
        if isinstance(remote, str) and "/" in remote:
            return remote.strip()
        return None
