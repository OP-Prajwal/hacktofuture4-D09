from __future__ import annotations

import json
import os
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


class OrchestratorLLM:
    """
    Central home for all LLM usage in the orchestrator.

    If you want to swap providers or models later, change this file only.
    The rest of the codebase should call this class and never import provider
    SDKs or LangChain model wrappers directly.
    """

    def __init__(self, settings: LLMSettings | None = None):
        self.settings = settings or LLMSettings(
            provider=os.getenv("NEXUS_LLM_PROVIDER", "disabled"),
            model=os.getenv("NEXUS_LLM_MODEL", "disabled"),
        )
        self._client: BaseChatModel | None = None

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
            text = getattr(response, "content", response)
            return self._parse_hypotheses_response(text, incident, locations, historical)
        except Exception:
            return self._fallback_hypotheses(incident, locations, historical)

    def is_enabled(self) -> bool:
        return self.settings.provider != "disabled" and self.settings.model != "disabled"

    def _get_client(self) -> BaseChatModel | None:
        if self._client is not None:
            return self._client

        provider = self.settings.provider.lower()
        if provider == "openai":
            try:
                from langchain_openai import ChatOpenAI
            except Exception:
                return None

            self._client = ChatOpenAI(
                model=self.settings.model,
                temperature=self.settings.temperature,
            )
            return self._client

        return None

    def _parse_hypotheses_response(
        self,
        raw_text: Any,
        incident: IncidentInput,
        locations: list[CodeLocation],
        historical: list[HistoricalIncident],
    ) -> list[Hypothesis]:
        try:
            if isinstance(raw_text, list):
                text = "".join(str(item) for item in raw_text)
            else:
                text = str(raw_text)
            data = json.loads(text)
            items = data.get("hypotheses", data)
            hypotheses = [Hypothesis.model_validate(item) for item in items]
            if hypotheses:
                hypotheses.sort(key=lambda item: item.confidence, reverse=True)
                return hypotheses[:5]
        except Exception:
            pass
        return self._fallback_hypotheses(incident, locations, historical)

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
                        "Add a graph-localization node backed by Neo4j for call-chain analysis.",
                        "Integrate observability MCP sources for traces and error group metadata.",
                    ],
                )
            )

        hypotheses.sort(key=lambda item: item.confidence, reverse=True)
        return hypotheses[:5]
