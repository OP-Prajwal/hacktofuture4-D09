from orchestrator.llm import LLMSettings, OrchestratorLLM
from orchestrator.models import IncidentInput


def test_llm_fallback_extract_search_terms():
    llm = OrchestratorLLM(LLMSettings(provider="disabled", model="disabled"))
    incident = IncidentInput(
        id="inc-123",
        title="Payment failure",
        service="checkout-api",
        environment="production",
        error_summary="TypeError: payment_id is undefined",
        stack_trace="TypeError: payment_id is undefined\n  at processPayment (checkout.js:42)",
        logs=["2026-04-15 12:00:00 ERROR: failed to process payment"],
    )
    terms = llm.extract_search_terms(incident)
    assert "payment_id" in terms
    assert "undefined" in terms
    assert "checkout-api" in terms


def test_llm_fallback_summarize():
    llm = OrchestratorLLM(LLMSettings(provider="disabled", model="disabled"))
    incident = IncidentInput(
        id="inc-123",
        title="Payment failure",
        service="checkout-api",
        environment="production",
        error_summary="TypeError: payment_id is undefined",
    )
    summary = llm.summarize_incident(incident)
    assert summary == incident.error_summary


def test_llm_fallback_hypotheses():
    llm = OrchestratorLLM(LLMSettings(provider="disabled", model="disabled"))
    incident = IncidentInput(
        id="inc-123",
        title="Payment failure",
        service="checkout-api",
        environment="production",
        error_summary="TypeError: payment_id is undefined",
    )
    hypotheses = llm.generate_hypotheses(incident, [], [])
    assert len(hypotheses) > 0
    assert "Insufficient evidence" in hypotheses[0].title
