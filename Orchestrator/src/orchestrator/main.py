from __future__ import annotations

import argparse
import json
from pathlib import Path

from orchestrator.connectors import ConnectorRegistry, StaticIncidentMemoryConnector
from orchestrator.llm import LLMSettings, OrchestratorLLM
from orchestrator.models import IncidentInput
from orchestrator.services import RepositoryLocator


def main() -> None:
    parser = argparse.ArgumentParser(description="NEXUS-X incident orchestrator")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run incident analysis")
    run_parser.add_argument("incident_file", type=Path, help="Path to incident JSON")
    run_parser.add_argument("--repo-root", type=Path, default=None, help="Repository root to inspect")
    run_parser.add_argument("--graph-project", default=None, help="Override Nexus Code Graph project scope. Defaults to repo_root/.nexus/config.json remote")
    run_parser.add_argument("--memory-dir", type=Path, default=None, help="Directory of historical incidents")
    run_parser.add_argument("--output-dir", type=Path, default=Path("reports"), help="Report output directory")
    run_parser.add_argument("--mcp-config", type=Path, default=None, help="Path to MCP server configuration JSON")
    run_parser.add_argument("--llm-provider", default="disabled", help="LLM provider name, e.g. openai")
    run_parser.add_argument("--llm-model", default="disabled", help="LLM model name")
    run_parser.add_argument("--llm-base-url", default=None, help="Base URL for local LLM providers")

    doctor_parser = subparsers.add_parser("doctor", help="Validate orchestrator dependencies and graph scope")
    doctor_parser.add_argument("--repo-root", type=Path, default=None, help="Repository root to inspect")
    doctor_parser.add_argument("--graph-project", default=None, help="Override Nexus Code Graph project scope. Defaults to repo_root/.nexus/config.json remote")

    args = parser.parse_args()

    if args.command == "run":
        from orchestrator.workflow import build_workflow

        incident = _load_incident(args.incident_file)
        registry = ConnectorRegistry()
        if args.memory_dir is not None:
            registry.add(StaticIncidentMemoryConnector(args.memory_dir))
        if args.mcp_config is not None:
            registry.load_mcp_config(args.mcp_config)

        llm = OrchestratorLLM(
            LLMSettings(
                provider=args.llm_provider,
                model=args.llm_model,
                base_url=args.llm_base_url,
            )
        )

        app = build_workflow(
            connector_registry=registry,
            repo_root=args.repo_root,
            graph_project=args.graph_project,
            output_dir=args.output_dir,
            llm=llm,
        )
        result = app.invoke({"incident": incident, "repo_root": args.repo_root})
        print(f"Report written to {result['report_path']}")
    elif args.command == "doctor":
        locator = RepositoryLocator(args.repo_root, graph_project=args.graph_project)
        print(json.dumps(locator.describe(), indent=2))


def _load_incident(path: Path) -> IncidentInput:
    data = json.loads(path.read_text(encoding="utf-8"))
    return IncidentInput.model_validate(data)


if __name__ == "__main__":
    main()
