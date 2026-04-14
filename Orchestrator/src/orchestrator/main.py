from __future__ import annotations

import argparse
import json
from pathlib import Path

from orchestrator.connectors import ConnectorRegistry, StaticIncidentMemoryConnector
from orchestrator.llm import LLMSettings, OrchestratorLLM
from orchestrator.models import IncidentInput
from orchestrator.workflow import build_workflow


def main() -> None:
    parser = argparse.ArgumentParser(description="NEXUS-X incident orchestrator")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run incident analysis")
    run_parser.add_argument("incident_file", type=Path, help="Path to incident JSON")
    run_parser.add_argument("--repo-root", type=Path, default=None, help="Repository root to inspect")
    run_parser.add_argument("--graph-project", default=None, help="Project scope in Neo4j, e.g. workspace_slug/project_slug")
    run_parser.add_argument("--memory-dir", type=Path, default=None, help="Directory of historical incidents")
    run_parser.add_argument("--output-dir", type=Path, default=Path("reports"), help="Report output directory")
    run_parser.add_argument("--llm-provider", default="disabled", help="LLM provider name, e.g. openai")
    run_parser.add_argument("--llm-model", default="disabled", help="LLM model name")

    args = parser.parse_args()

    if args.command == "run":
        incident = _load_incident(args.incident_file)
        registry = ConnectorRegistry()
        if args.memory_dir is not None:
            registry.add(StaticIncidentMemoryConnector(args.memory_dir))
        llm = OrchestratorLLM(
            LLMSettings(
                provider=args.llm_provider,
                model=args.llm_model,
            )
        )

        app = build_workflow(
            connector_registry=registry,
            repo_root=args.repo_root,
            graph_project=args.graph_project,
            output_dir=args.output_dir,
            llm=llm,
        )
        result = app.invoke({"incident": incident})
        print(f"Report written to {result['report_path']}")


def _load_incident(path: Path) -> IncidentInput:
    data = json.loads(path.read_text(encoding="utf-8"))
    return IncidentInput.model_validate(data)


if __name__ == "__main__":
    main()
