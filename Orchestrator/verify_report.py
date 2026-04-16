import os
import sys

# Add src to sys path
sys.path.append(os.path.abspath("src"))

from pathlib import Path
from orchestrator.models import IncidentInput, Hypothesis
from orchestrator.agents.reporting import write_report
from orchestrator.llm import OrchestratorLLM, LLMSettings
from orchestrator.state import OrchestratorState

incident = IncidentInput(
    id="inc-999",
    title="Test Incident",
    service="Test Service",
    environment="Test Env",
    error_summary="Test Error",
    stack_trace="Test Stack",
    logs=[],
    tags=[]
)

llm = OrchestratorLLM(LLMSettings(provider="disabled", model="disabled"))

# Generate fallback hypotheses
hypotheses = llm.generate_hypotheses(incident, [], [])
print(f"Generated {len(hypotheses)} hypotheses.")

state = {"incident": incident, "hypotheses": hypotheses}

output = write_report(state, Path("test-reports"), llm)
print(f"Report written to {output['report_path']}")
