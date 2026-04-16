from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from orchestrator.models import CodeLocation, HistoricalIncident, Hypothesis, IncidentInput


@dataclass
class LLMSettings:
    provider: str = "disabled"
    model: str = "disabled"
    temperature: float = 0.1
    base_url: str | None = None


class OrchestratorLLM:
    """
    Central home for all LLM usage in the orchestrator.

    If you want to swap providers or models later, change this file only.
    The rest of the codebase should call this class and never import provider
    SDKs or LangChain model wrappers directly.
    """

    def __init__(self, settings: LLMSettings | None = None):
        self.settings = settings or LLMSettings(
            provider=os.getenv("NEXUS_LLM_PROVIDER", "ollama"),
            model=os.getenv("NEXUS_LLM_MODEL", "qwen2.5-coder"),
            base_url=os.getenv("NEXUS_LLM_BASE_URL", "http://localhost:11434"),
        )
        self._client: BaseChatModel | None = None

    def extract_search_terms(self, incident: IncidentInput) -> list[str]:
        """
        Extract key search terms for querying external systems.
        Falls back to regex-based extraction if LLM is disabled.
        """
        if not self.is_enabled():
            return self._fallback_extract_search_terms(incident)

        client = self._get_client()
        if client is None:
            return self._fallback_extract_search_terms(incident)

        payload = {
            "title": incident.title,
            "service": incident.service,
            "error_summary": incident.error_summary,
            "stack_trace": incident.stack_trace[:1000] if incident.stack_trace else "",
        }
        messages = [
            SystemMessage(
                content=(
                    "You are an incident triage assistant. Extract up to 15 key technical search terms "
                    "from this incident that would be most effective for searching Slack, logs, and "
                    "incident trackers. Return a JSON array of strings only."
                )
            ),
            HumanMessage(content=json.dumps(payload)),
        ]

        try:
            response = client.invoke(messages)
            text = self._get_content(response)
            terms = json.loads(self._sanitize_json(text))
            if isinstance(terms, list):
                return [str(t).lower() for t in terms if t][:15]
        except Exception:
            pass
        return self._fallback_extract_search_terms(incident)

    def generate_hypotheses(
        self,
        incident: IncidentInput,
        locations: list[CodeLocation],
        historical: list[HistoricalIncident],
    ) -> list[Hypothesis]:
        if not self.is_enabled():
            return self._fallback_hypotheses(incident, locations, historical)

        client = self._get_client()
        if client is None:
            return self._fallback_hypotheses(incident, locations, historical)

        payload = {
            "incident": incident.model_dump(),
            "candidate_locations": [item.model_dump() for item in locations[:5]],
            "historical_incidents": [item.model_dump() for item in historical[:5]],
        }
        messages = [
            SystemMessage(
                content=(
                    "You are an incident-analysis model. Return JSON only. "
                    "Produce up to 5 ranked root-cause hypotheses. Each hypothesis must have "
                    "title, confidence, evidence, likely_locations, next_steps."
                )
            ),
            HumanMessage(content=json.dumps(payload)),
        ]

        try:
            response = client.invoke(messages)
            text = self._get_content(response)
            return self._parse_hypotheses_response(text, incident, locations, historical)
        except Exception:
            return self._fallback_hypotheses(incident, locations, historical)

    def summarize_incident(self, incident: IncidentInput) -> str:
        """
        Create a concise one-paragraph summary of the incident for the report.
        """
        if not self.is_enabled():
            return incident.error_summary

        client = self._get_client()
        if client is None:
            return incident.error_summary

        messages = [
            SystemMessage(
                content="Summarize this production incident in 2-3 clear sentences for a technical report."
            ),
            HumanMessage(
                content=f"Title: {incident.title}\nService: {incident.service}\nError: {incident.error_summary}"
            ),
        ]

        try:
            response = client.invoke(messages)
            return self._get_content(response).strip()
        except Exception:
            return incident.error_summary

    def is_enabled(self) -> bool:
        return self.settings.provider != "disabled" and self.settings.model != "disabled"

    def _get_client(self) -> BaseChatModel | None:
        if self._client is not None:
            return self._client

        provider = self.settings.provider.lower()
        if provider == "openai":
            try:
                from langchain_openai import ChatOpenAI
                self._client = ChatOpenAI(
                    model=self.settings.model,
                    temperature=self.settings.temperature,
                )
            except Exception:
                return None
        elif provider == "local":
            # Generic OpenAI-compatible local provider (LM Studio, LocalAI, etc.)
            try:
                from langchain_openai import ChatOpenAI
                self._client = ChatOpenAI(
                    model=self.settings.model,
                    temperature=self.settings.temperature,
                    base_url=self.settings.base_url or "http://localhost:1234/v1",
                    api_key="not-needed",
                )
            except Exception:
                return None
        elif provider == "ollama":
            try:
                from langchain_ollama import ChatOllama
                self._client = ChatOllama(
                    model=self.settings.model,
                    temperature=self.settings.temperature,
                    base_url=self.settings.base_url or "http://localhost:11434",
                )
            except Exception:
                return None
        elif provider == "anthropic":
            try:
                from langchain_anthropic import ChatAnthropic
                self._client = ChatAnthropic(
                    model=self.settings.model,
                    temperature=self.settings.temperature,
                )
            except Exception:
                return None
        elif provider == "google":
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI
                self._client = ChatGoogleGenerativeAI(
                    model=self.settings.model,
                    temperature=self.settings.temperature,
                )
            except Exception:
                return None

        return self._client

    def _get_content(self, response: Any) -> str:
        if hasattr(response, "content"):
            return str(response.content)
        return str(response)

    def _sanitize_json(self, text: str) -> str:
        # Remove markdown code blocks if present
        text = re.sub(r"```json\s*", "", text)
        text = re.sub(r"```\s*", "", text)
        return text.strip()

    def _parse_hypotheses_response(
        self,
        raw_text: str,
        incident: IncidentInput,
        locations: list[CodeLocation],
        historical: list[HistoricalIncident],
    ) -> list[Hypothesis]:
        try:
            data = json.loads(self._sanitize_json(raw_text))
            items = data.get("hypotheses", data)
            if not isinstance(items, list):
                items = [items]
            hypotheses = [Hypothesis.model_validate(item) for item in items]
            if hypotheses:
                hypotheses.sort(key=lambda item: item.confidence, reverse=True)
                return hypotheses[:5]
        except Exception:
            pass
        return self._fallback_hypotheses(incident, locations, historical)

    def _fallback_extract_search_terms(self, incident: IncidentInput) -> list[str]:
        texts = [
            incident.error_summary,
            incident.stack_trace or "",
            " ".join(incident.logs[:10]),
            incident.service,
        ]
        tokens: list[str] = []
        for text in texts:
            tokens.extend(re.findall(r"[A-Za-z_][A-Za-z0-9_\-/.:]{2,}", text))

        normalized: list[str] = []
        seen = set()
        for token in tokens:
            cleaned = token.strip(".,:;()[]{}<>").lower()
            if len(cleaned) < 3:
                continue
            if cleaned in seen:
                continue
            seen.add(cleaned)
            normalized.append(cleaned)
        return normalized[:15]

    def _fallback_hypotheses(
        self,
        incident: IncidentInput,
        locations: list[CodeLocation],
        historical: list[HistoricalIncident],
    ) -> list[Hypothesis]:
        hypotheses: list[Hypothesis] = []

        if locations:
            top = locations[0]
            hypotheses.append(
                Hypothesis(
                    title="Application code regression in the localized failure area",
                    confidence=min(0.55 + top.confidence * 0.4, 0.95),
                    evidence=[
                        f"Top candidate path: {top.path}",
                        f"Localization rationale: {top.rationale}",
                        f"Observed error: {incident.error_summary}",
                    ],
                    likely_locations=[top.path],
                    next_steps=[
                        "Inspect the surrounding function and recent edits in this file.",
                        "Verify whether the failing input shape matches the stack trace.",
                        "Check whether the error started after a recent deployment.",
                    ],
                )
            )

        if historical:
            top_hist = historical[0]
            hypotheses.append(
                Hypothesis(
                    title="Failure mode resembles a previously seen production incident",
                    confidence=min(0.45 + top_hist.confidence * 0.4, 0.9),
                    evidence=[
                        f"Historical match: {top_hist.title}",
                        f"Historical source: {top_hist.source}",
                        f"Historical summary: {top_hist.summary[:180]}",
                    ],
                    likely_locations=[loc.path for loc in locations[:3]],
                    next_steps=[
                        "Compare the current logs and configuration against the previous incident.",
                        "Validate whether the old fix still applies in the current code path.",
                    ],
                )
            )

        if not hypotheses:
            hypotheses.append(
                Hypothesis(
                    title="Insufficient evidence for exact localization yet",
                    confidence=0.25,
                    evidence=[
                        "No repository match was found from the current stack trace and log terms.",
                        "No historical incident match was found in configured knowledge connectors.",
                    ],
                    likely_locations=[],
                    next_steps=[
                        "Add deploy metadata and recent diffs to the incident payload.",
                        "Verify that the configured Nexus-X API URL containing the expected code graph is reachable.",
                        "Integrate observability MCP sources for traces and error group metadata.",
                    ],
                )
            )

        hypotheses.sort(key=lambda item: item.confidence, reverse=True)
        return hypotheses[:5]
