# NEXUS-X Orchestrator

This package contains the first cut of the production incident orchestrator.

It is intentionally narrow:

- ingest a production incident payload
- extract structured evidence from logs and stack traces
- query external incident-intelligence connectors
- inspect the local repository for likely code locations
- rank candidate root-cause hypotheses
- generate a structured Markdown incident report

## Why this shape

The orchestrator should not start as a "chat agent that calls everything".
It should start as an evidence pipeline with a small graph of specialist steps.

This package uses:

- `langgraph` for workflow orchestration
- `langchain-core` for future LLM integration points
- `pydantic` for incident and report schemas

## LLM isolation

All LLM-related code lives in:

- `src/orchestrator/llm.py`

If you want to change the model or provider later, update that file only.
Other modules should call the `OrchestratorLLM` interface and must not import
provider SDKs directly.

## Current workflow

1. `triage`
2. `observability_agent`
3. `slack_agent`
4. `tracker_agent`
5. `docs_agent`
6. `merge_context`
7. `localize_code`
8. `rank_hypotheses`
9. `write_report`

## Agent roles

- `main_orchestrator`
- `triage_agent`
- `observability_agent`
- `slack_agent`
- `tracker_agent`
- `docs_agent`
- `repo_localization_agent`
- `hypothesis_agent`
- `report_agent`

## Connector model

The package now separates:

- agent nodes in the LangGraph workflow
- connector registry and routing
- MCP adapter interfaces

Included adapters:

- `SlackMCPConnector`
- `IncidentTrackerMCPConnector`
- `DocsRunbookMCPConnector`
- `ObservabilityMCPConnector`
- `StaticIncidentMemoryConnector`

The MCP-backed connectors depend on an `MCPClient` interface. That lets you
plug in real MCP implementations later without rewriting agent logic.

## Suggested v1 external MCP priorities

1. Observability
2. Slack
3. Incident tracker
4. Internal docs / runbooks
5. Public web knowledge as fallback only

## Install

```bash
cd Orchestrator
pip install -e .
```

## Nexus-X Graph localization

The orchestrator can query the NEXUS-X code intelligence graph via the backend API.
Set these variables in `Orchestrator/.env`:

```env
NEXUS_API_URL=http://localhost:8000
NEXUS_GRAPH_PROJECT=workspace_slug/project_slug
```

`NEXUS_GRAPH_PROJECT` is the required tenant/project isolation key. Every lookup is scoped to that exact `project` value.

If you pass `--repo-root`, the orchestrator now derives the graph scope automatically from `repo_root/.nexus/config.json` using its `remote` value. That should match the project the agent was spawned from. Use `--graph-project` only to override it.

Validate the setup before running a full incident:

```bash
python -m orchestrator.main doctor --repo-root ../test-repo
```

## Run

```bash
nexus-orchestrator run sample-incident.json --repo-root ../test-repo --memory-dir ./memory
```

With an LLM enabled:

```bash
nexus-orchestrator run sample-incident.json --repo-root ../test-repo --memory-dir ./memory --llm-provider ollama --llm-model qwen2.5-coder
```

You can also run it as a module:

```bash
python -m orchestrator.main run sample-incident.json --repo-root ../test-repo --memory-dir ./memory
```

To override the graph scope at runtime:

```bash
nexus-orchestrator run sample-incident.json --repo-root ../test-repo --memory-dir ./memory
```

Override example:

```bash
nexus-orchestrator run sample-incident.json --graph-project acme-corp/api-server --repo-root ../test-repo --memory-dir ./memory
```

## Input incident shape

```json
{
  "id": "inc-001",
  "title": "Checkout requests failing",
  "service": "payments-api",
  "environment": "production",
  "error_summary": "TypeError: cannot read properties of undefined",
  "stack_trace": "TypeError: ...",
  "logs": [
    "2026-04-14T12:00:00Z ERROR checkout failed for user 42",
    "2026-04-14T12:00:01Z ERROR payment provider returned 500"
  ]
}
```

## Output

The workflow writes a Markdown report with:

- incident summary
- extracted evidence
- likely code locations
- similar historical incidents
- ranked root-cause hypotheses
- recommended next steps

## Recommended next additions

- Git diff and deploy correlation node
- real MCP clients for Slack, PagerDuty, Jira, Confluence, Sentry, Datadog
- approval-gated remediation workflow
- JSON report output alongside Markdown
