from pathlib import Path
from unittest.mock import MagicMock

from orchestrator.models import IncidentInput
from orchestrator.workflow import build_workflow


def test_workflow_execution(tmp_path):
    incident = IncidentInput(
        id="inc-123",
        title="Test Incident",
        service="test-service",
        environment="staging",
        error_summary="Something went wrong",
    )
    
    # Mocking connectors registry to avoid real external calls
    registry = MagicMock()
    # Mocking registry.add and search if needed, but build_workflow uses its own defaults if not provided
    
    # Use tmp_path for reports
    app = build_workflow(
        connector_registry=registry,
        output_dir=tmp_path,
        # LLM defaults to disabled which uses fallbacks
    )
    
    initial_state = {"incident": incident}
    final_state = app.invoke(initial_state)
    
    assert "report_path" in final_state
    assert "report_markdown" in final_state
    assert Path(final_state["report_path"]).exists()
    assert "# Incident Report: Test Incident" in final_state["report_markdown"]
    assert "Something went wrong" in final_state["report_markdown"]
