from __future__ import annotations

from orchestrator.models import AgentRole


def get_default_agent_roles() -> list[AgentRole]:
    return [
        AgentRole(
            name="main_orchestrator",
            responsibility="Coordinates the incident workflow and merges specialist outputs.",
            tool_domains=["workflow", "reporting"],
        ),
        AgentRole(
            name="triage_agent",
            responsibility="Extracts structured error terms, stack trace clues, and core evidence.",
            tool_domains=["logs", "parsing"],
        ),
        AgentRole(
            name="observability_agent",
            responsibility="Searches monitoring and incident telemetry systems for matching failures.",
            tool_domains=["observability"],
        ),
        AgentRole(
            name="slack_agent",
            responsibility="Searches prior incident discussions and owner conversations in Slack.",
            tool_domains=["slack"],
        ),
        AgentRole(
            name="tracker_agent",
            responsibility="Looks for similar tickets, RCAs, and previously recorded incidents.",
            tool_domains=["tracker"],
        ),
        AgentRole(
            name="docs_agent",
            responsibility="Searches runbooks and internal documentation for known fixes.",
            tool_domains=["docs"],
        ),
        AgentRole(
            name="repo_localization_agent",
            responsibility="Maps failure evidence to likely code files and symbols in the repository.",
            tool_domains=["repo", "nexus_api"],
        ),
        AgentRole(
            name="hypothesis_agent",
            responsibility="Ranks root-cause hypotheses using evidence and prior incidents.",
            tool_domains=["reasoning"],
        ),
        AgentRole(
            name="report_agent",
            responsibility="Produces the final incident Markdown report.",
            tool_domains=["reporting"],
        ),
    ]
