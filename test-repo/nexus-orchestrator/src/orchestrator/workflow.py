from __future__ import annotations

from functools import partial
from pathlib import Path

from langgraph.graph import END, START, StateGraph

from orchestrator.agents import (
    collect_docs_context,
    collect_observability_context,
    collect_slack_context,
    collect_tracker_context,
    merge_external_context,
    localize_code,
    rank_hypotheses,
    triage_incident,
    write_report,
)
from orchestrator.connectors import ConnectorRegistry
from orchestrator.llm import OrchestratorLLM
from orchestrator.services import RepositoryLocator
from orchestrator.state import OrchestratorState


def build_workflow(
    connector_registry: ConnectorRegistry | None = None,
    repo_root: Path | None = None,
    graph_project: str | None = None,
    output_dir: Path | None = None,
    llm: OrchestratorLLM | None = None,
):
    registry = connector_registry or ConnectorRegistry()
    locator = RepositoryLocator(repo_root, graph_project=graph_project)
    reports_dir = output_dir or Path("reports")
    orchestrator_llm = llm or OrchestratorLLM()

    graph = StateGraph(OrchestratorState)
    graph.add_node("triage", partial(triage_incident, llm=orchestrator_llm))
    graph.add_node("observability_agent", partial(collect_observability_context, registry=registry))
    graph.add_node("slack_agent", partial(collect_slack_context, registry=registry))
    graph.add_node("tracker_agent", partial(collect_tracker_context, registry=registry))
    graph.add_node("docs_agent", partial(collect_docs_context, registry=registry))
    graph.add_node("merge_context", merge_external_context)
    graph.add_node("localize_code", partial(localize_code, locator=locator))
    graph.add_node("rank_hypotheses", partial(rank_hypotheses, llm=orchestrator_llm))
    graph.add_node("write_report", partial(write_report, output_dir=reports_dir, llm=orchestrator_llm))

    graph.add_edge(START, "triage")
    graph.add_edge("triage", "observability_agent")
    graph.add_edge("observability_agent", "slack_agent")
    graph.add_edge("slack_agent", "tracker_agent")
    graph.add_edge("tracker_agent", "docs_agent")
    graph.add_edge("docs_agent", "merge_context")
    graph.add_edge("merge_context", "localize_code")
    graph.add_edge("localize_code", "rank_hypotheses")
    graph.add_edge("rank_hypotheses", "write_report")
    graph.add_edge("write_report", END)
    return graph.compile()
