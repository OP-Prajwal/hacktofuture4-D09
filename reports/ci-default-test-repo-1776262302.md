# Incident Report: CI Build Failed: default/test-repo

## Summary
- Incident ID: `ci-default-test-repo-1776262302`
- Service: `test-repo`
- Environment: `ci`
- Generated At: `2026-04-15T14:12:08.544881+00:00`
- Overview: The CI build failed for the test-repo service due to a TypeError in the broken_service.py file. The error occurred on line 17 of the script, where an attempt was made to add a NoneType value to an int variable. This resulted in the traceback provided in the error message.
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
- `broken_service.py` confidence `0.63`: matched Neo4j project-scoped code graph, matched extracted symbol, summary overlaps incident terms, blast radius 3, 1 immediate graph links
- `broken_service.py:1` confidence `0.37`: matched Neo4j project-scoped code graph, blast radius 2, 1 immediate graph links
- `broken_service.py:14` confidence `0.16`: matched incident search terms
- `README.md:1` confidence `0.16`: matched incident search terms
- `.gitnexus/meta.json:2` confidence `0.16`: matched incident search terms
- `.nexus/config.json:2` confidence `0.16`: matched incident search terms
- `AGENTS.md:4` confidence `0.08`: matched incident search terms
- `CLAUDE.md:4` confidence `0.08`: matched incident search terms

## Similar Historical Incidents
- No similar incidents found in configured connectors.

## Ranked Root Cause Hypotheses
### 1. Application code regression in the localized failure area
- Confidence: `0.80`
- Evidence:
  - Top candidate path: broken_service.py
  - Localization rationale: matched Neo4j project-scoped code graph, matched extracted symbol, summary overlaps incident terms, blast radius 3, 1 immediate graph links
  - Observed error: Traceback (most recent call last):
  File "C:\nexus-X\test-repo\broken_service.py", line 17, in <module>
    result = calculate_total(cart)
  File "C:\nexus-X\test-repo\broken_service.py", line 6, in calculate_total
    total += item['price']
TypeError: unsupported operand type(s) for +=: 'int' and 'NoneType'
- Likely Locations:
  - `broken_service.py`
- Recommended Next Steps:
  - Inspect the surrounding function and recent edits in this file.
  - Verify whether the failing input shape matches the stack trace.
  - Check whether the error started after a recent deployment.
