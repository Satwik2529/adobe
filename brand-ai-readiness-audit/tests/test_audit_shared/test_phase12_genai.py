import pytest
import asyncio
from audit_shared.genai.client import GenAIClient, RateLimitError
from audit_shared.genai.engine import GenAIEngine
from audit_shared.models.finding import Finding, Severity, Trigger, TriggerType, Evidence, SuggestedAction
from audit_shared.models.grouping import GroupingResult, EvaluationScope

def create_mock_group(finding_id: str, evidence_observed_value: str = "mock", affected_count: int = 5):
    f = Finding(
        id=finding_id,
        pipeline=None,
        title=f"Test Finding {finding_id}",
        severity=Severity.HIGH,
        trigger=Trigger(rule_id="test", type=TriggerType.DETERMINISTIC),
        evidence=Evidence(observed_value=evidence_observed_value),
        suggested_action=SuggestedAction(summary="Fix it", priority=None)
    )
    return GroupingResult(
        group_id=f"sig_{finding_id}",
        canonical_finding=f,
        source_finding_ids=[f.id for _ in range(affected_count)],
        source_findings=[f for _ in range(affected_count)]
    )

def test_genai_success():
    client = GenAIClient(use_mock=True)
    engine = GenAIEngine(client=client)
    
    group = create_mock_group("F1")
    diag = asyncio.run(engine.enrich_groups([group]))
    
    assert diag.requests_attempted == 1
    assert diag.successful == 1
    assert diag.invalid_responses == 0
    assert group.canonical_finding.genai.used is True
    assert "This is a generalized explanation" in group.canonical_finding.genai.explanation
    assert group.canonical_finding.genai.why_it_matters == "It matters because search engines need clear guidance."
    assert group.canonical_finding.genai.possible_solution == "Implement the suggested best practices."
    
    assert group.canonical_finding.severity == Severity.HIGH
    assert group.canonical_finding.evidence.observed_value == "mock"

def test_genai_one_request_per_group():
    client = GenAIClient(use_mock=True)
    engine = GenAIEngine(client=client)
    
    g1 = create_mock_group("F1", affected_count=30)
    g2 = create_mock_group("F2", affected_count=5)
    
    diag = asyncio.run(engine.enrich_groups([g1, g2]))
    
    assert diag.requests_attempted == 2
    assert diag.successful == 2

def test_genai_429_recover():
    client = GenAIClient(use_mock=True)
    engine = GenAIEngine(client=client)
    
    g = create_mock_group("F1", evidence_observed_value="mock_429_recover")
    diag = asyncio.run(engine.enrich_groups([g]))
    
    assert diag.requests_attempted == 1
    assert diag.successful == 1
    assert "Recovered from 429!" in g.canonical_finding.genai.explanation

def test_genai_429_exhaust():
    client = GenAIClient(use_mock=True, max_retries=1)
    engine = GenAIEngine(client=client)
    
    g = create_mock_group("F1", evidence_observed_value="mock_429_exhaust")
    diag = asyncio.run(engine.enrich_groups([g]))
    
    assert diag.requests_attempted == 1
    assert diag.successful == 0
    assert diag.rate_limited == 1
    assert g.canonical_finding.genai.used is False
    assert g.canonical_finding.genai.explanation is None

def test_genai_timeout():
    client = GenAIClient(use_mock=True, timeout=0.1)
    engine = GenAIEngine(client=client)
    
    g = create_mock_group("F1", evidence_observed_value="mock_timeout")
    diag = asyncio.run(engine.enrich_groups([g]))
    
    assert diag.requests_attempted == 1
    assert diag.successful == 0
    assert diag.timeouts == 1
    assert g.canonical_finding.genai.used is False

def test_genai_provider_failure():
    client = GenAIClient(use_mock=True, max_retries=0)
    engine = GenAIEngine(client=client)
    
    g = create_mock_group("F1", evidence_observed_value="mock_500")
    diag = asyncio.run(engine.enrich_groups([g]))
    
    assert diag.requests_attempted == 1
    assert diag.successful == 0
    assert diag.provider_failures == 1
    assert g.canonical_finding.genai.used is False

def test_genai_invalid_type():
    client = GenAIClient(use_mock=True)
    engine = GenAIEngine(client=client)
    
    g = create_mock_group("F1", evidence_observed_value="mock_invalid_type")
    diag = asyncio.run(engine.enrich_groups([g]))
    
    assert diag.requests_attempted == 1
    assert diag.successful == 0
    assert diag.invalid_responses == 1
    assert g.canonical_finding.genai.used is False

def test_genai_missing_field():
    client = GenAIClient(use_mock=True)
    engine = GenAIEngine(client=client)
    
    g = create_mock_group("F1", evidence_observed_value="mock_missing_field")
    diag = asyncio.run(engine.enrich_groups([g]))
    
    assert diag.requests_attempted == 1
    assert diag.successful == 0
    assert diag.invalid_responses == 1
    assert g.canonical_finding.genai.used is False

def test_genai_empty_string():
    client = GenAIClient(use_mock=True)
    engine = GenAIEngine(client=client)
    
    g = create_mock_group("F1", evidence_observed_value="mock_empty_string")
    diag = asyncio.run(engine.enrich_groups([g]))
    
    assert diag.requests_attempted == 1
    assert diag.successful == 0
    assert diag.invalid_responses == 1
    assert g.canonical_finding.genai.used is False

def test_genai_global_budget():
    client = GenAIClient(use_mock=True, timeout=2.0)
    engine = GenAIEngine(client=client, global_budget_seconds=0.0)
    
    g = create_mock_group("F1")
    diag = asyncio.run(engine.enrich_groups([g]))
    
    assert diag.requests_attempted == 0
    assert diag.skipped_by_budget == 1
    assert not hasattr(g.canonical_finding, "genai") or not g.canonical_finding.genai

def test_genai_insufficient_evidence():
    client = GenAIClient(use_mock=True)
    engine = GenAIEngine(client=client)
    
    g = create_mock_group("F1", evidence_observed_value=None)
    diag = asyncio.run(engine.enrich_groups([g]))
    
    assert diag.eligible_groups == 0
    assert diag.requests_attempted == 0
    assert diag.successful == 0
