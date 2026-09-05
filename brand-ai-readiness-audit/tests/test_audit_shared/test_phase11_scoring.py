import pytest
from audit_shared.reporting.scoring import ScoringEngine, ScoringConfig
from audit_shared.models.finding import Finding, Severity, Trigger, TriggerType, Pipeline, generate_finding_id

def create_mock_finding(severity: Severity) -> Finding:
    from audit_shared.models.finding import Evidence, SuggestedAction, ActionPriority
    return Finding(
        id=generate_finding_id("TEST-001", ["url"]),
        pipeline=Pipeline.AI_DISCOVERABILITY,
        title="Test Finding",
        severity=severity,
        trigger=Trigger(rule_id="TEST-001", type=TriggerType.DETERMINISTIC),
        evidence=Evidence(observed_value="test"),
        suggested_action=SuggestedAction(summary="Fix it", priority=ActionPriority.HIGH)
    )

def test_scoring_critical_finding_deducts_50():
    # Verify that a single critical finding deducting 50% correctly yields a final score of 50
    engine = ScoringEngine(ScoringConfig())
    finding = create_mock_finding(Severity.CRITICAL)
    score = engine.calculate_score([finding])
    assert score == 50

def test_scoring_high_medium_low_deducts_correctly():
    engine = ScoringEngine(ScoringConfig())
    findings = [
        create_mock_finding(Severity.HIGH), # 20
        create_mock_finding(Severity.MEDIUM), # 10
        create_mock_finding(Severity.LOW) # 5
    ]
    score = engine.calculate_score(findings)
    assert score == 65 # 100 - 20 - 10 - 5

def test_scoring_floor_at_zero():
    engine = ScoringEngine(ScoringConfig())
    findings = [create_mock_finding(Severity.CRITICAL) for _ in range(3)] # 3 * 50 = 150
    score = engine.calculate_score(findings)
    assert score == 0
