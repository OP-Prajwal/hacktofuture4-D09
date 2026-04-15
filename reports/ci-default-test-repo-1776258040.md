# Incident Report: CI Build Failed: default/test-repo

## Summary
- Incident ID: `ci-default-test-repo-1776258040`
- Service: `test-repo`
- Environment: `ci`
- Generated At: `2026-04-15T13:01:38.779028+00:00`
- Overview: The CI build failed for the test-repo service due to a TypeError in the broken_service.py file. The error occurred on line 17 of the script, where an attempt was made to add a NoneType value to an integer variable total. This caused the build to fail and required investigation into the code to identify and fix the issue.
- Error Summary: Traceback (most recent call last):
  File "C:\nexus-X\test-repo\broken_service.py", line 17, in <module>
    result = calculate_total(cart)
  File "C:\nexus-X\test-repo\broken_service.py", line 6, in calculate_total
    total += item['price']
TypeError: unsupported operand type(s) for +=: 'int' and 'NoneType'

## Agent Roles
- `main_orchestrator`: Coordinates the incident workflow and merges specialist outputs. Tools: workflow, reporting
- `triage_agent`: Extracts structured error terms, stack trace clues, and core evidence. Tools: logs, parsing
- `observability_agent`: Searches monitoring and incident telemetry systems for matching failures. Tools: observability
- `slack_agent`: Searches prior incident discussions and owner conversations in Slack. Tools: slack
- `tracker_agent`: Looks for similar tickets, RCAs, and previously recorded incidents. Tools: tracker
- `docs_agent`: Searches runbooks and internal documentation for known fixes. Tools: docs
- `repo_localization_agent`: Maps failure evidence to likely code files and symbols in the repository. Tools: repo, neo4j_future
- `hypothesis_agent`: Ranks root-cause hypotheses using evidence and prior incidents. Tools: reasoning
- `report_agent`: Produces the final incident Markdown report. Tools: reporting

## Extracted Evidence
- `summary` from `triage` (trust `0.95`): Traceback (most recent call last):
  File "C:\nexus-X\test-repo\broken_service.py", line 17, in <module>
    result = calculate_total(cart)
  File "C:\nexus-X\test-repo\broken_service.py", line 6, in calculate_total
    total += item['price']
TypeError: unsupported operand type(s) for +=: 'int' and 'NoneType'

## Likely Code Locations
- No likely code locations found.

## Similar Historical Incidents
- No similar incidents found in configured connectors.

## Ranked Root Cause Hypotheses
### 1. Insufficient evidence for exact localization yet
- Confidence: `0.25`
- Evidence:
  - No repository match was found from the current stack trace and log terms.
  - No historical incident match was found in configured knowledge connectors.
- Recommended Next Steps:
  - Add deploy metadata and recent diffs to the incident payload.
  - Verify that the configured Neo4j project scope contains the expected code graph.
  - Integrate observability MCP sources for traces and error group metadata.
