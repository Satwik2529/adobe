import pytest
import json
from audit_shared.models.data_flow import CrawlDataset, PageRecord, CrawlStats, CrawlDiagnostics
from audit_shared.models.finding import (
    Finding, Severity, Pipeline, TriggerType, ActionPriority, Trigger, SuggestedAction,
    Evidence, AffectedPages, NLPContext, GenAIContext, generate_finding_id
)
from audit_shared.validation.finding_validator import FindingValidator

@pytest.fixture
def sample_dataset():
    # Setup a dummy dataset for provenance
    page = PageRecord(
        url="https://example.com/products/a",
        final_url="https://example.com/products/a",
        status_code=200,
        content_type="text/html",
        depth=1,
        parent_url="https://example.com/"
    )
    return CrawlDataset(
        seed_url="https://example.com/",
        crawled_at="2026-09-04T00:00:00Z",
        pages=[page],
        crawl_stats=CrawlStats(),
        crawl_diagnostics=CrawlDiagnostics()
    )

def test_1_valid_deterministic_finding(sample_dataset):
    evidence = Evidence(
        pages_checked=1,
        pages_affected=1,
        affected_percentage=100.0,
        affected_pages=AffectedPages(count=1, sample=["https://example.com/products/a"], truncated=False),
        details={"schema_analysis": {"product_schema_missing": 1}}
    )
    finding = Finding(
        id=generate_finding_id("AI-SCHEMA-010", ["deterministic-1"]),
        pipeline=Pipeline.AI_DISCOVERABILITY,
        title="No Product JSON-LD on product pages",
        severity=Severity.HIGH,
        trigger=Trigger(rule_id="AI-SCHEMA-010", type=TriggerType.DETERMINISTIC),
        evidence=evidence,
        suggested_action=SuggestedAction(summary="Add Product JSON-LD", priority=ActionPriority.HIGH)
    )
    errors = FindingValidator.validate(finding, sample_dataset)
    assert not errors

def test_2_valid_semantic_compatible_finding(sample_dataset):
    evidence = Evidence(
        page="https://example.com/products/a",
        observed_value="Cloud Security Services",
        field="title"
    )
    finding = Finding(
        id="AI-F-031",
        pipeline=Pipeline.AI_DISCOVERABILITY,
        title="Page content does not address topic",
        severity=Severity.MEDIUM,
        trigger=Trigger(rule_id="SEMANTIC_TOPIC_RELEVANCE", type=TriggerType.SEMANTIC),
        evidence=evidence,
        suggested_action=SuggestedAction(summary="Align content", priority=ActionPriority.MEDIUM)
    )
    errors = FindingValidator.validate(finding, sample_dataset)
    assert not errors

def test_3_missing_required_field(sample_dataset):
    evidence = Evidence(page="https://example.com/products/a")
    finding = Finding(
        id="", # Missing ID
        pipeline=Pipeline.AI_DISCOVERABILITY,
        title="Title",
        severity=Severity.LOW,
        trigger=Trigger(rule_id="RULE-1", type=TriggerType.DETERMINISTIC),
        evidence=evidence,
        suggested_action=SuggestedAction(summary="Fix", priority=ActionPriority.LOW)
    )
    errors = FindingValidator.validate(finding, sample_dataset)
    assert "Finding must have an ID." in errors

def test_4_5_6_7_invalid_enums():
    # Python Enums prevent instantiation with invalid values at construction time
    with pytest.raises(ValueError):
        Pipeline("invalid_pipeline")
    with pytest.raises(ValueError):
        Severity("invalid_severity")
    with pytest.raises(ValueError):
        TriggerType("invalid_trigger")
    with pytest.raises(ValueError):
        ActionPriority("invalid_priority")

def test_8_missing_evidence(sample_dataset):
    finding = Finding(
        id="F-1",
        pipeline=Pipeline.FRESHNESS,
        title="Title",
        severity=Severity.INFO,
        trigger=Trigger(rule_id="R-1", type=TriggerType.DETERMINISTIC),
        evidence=None, # Missing
        suggested_action=SuggestedAction(summary="Fix", priority=ActionPriority.LOW)
    )
    errors = FindingValidator.validate(finding, sample_dataset)
    assert "Finding must have evidence." in errors

def test_9_invalid_evidence_url(sample_dataset):
    evidence = Evidence(page="not_a_url")
    finding = Finding(
        id="F-1", pipeline=Pipeline.FRESHNESS, title="Title", severity=Severity.INFO,
        trigger=Trigger(rule_id="R", type=TriggerType.DETERMINISTIC),
        evidence=evidence, suggested_action=SuggestedAction(summary="F", priority=ActionPriority.LOW)
    )
    errors = FindingValidator.validate(finding, sample_dataset)
    assert any("Invalid URL format" in e for e in errors)

def test_10_evidence_referencing_unknown_page(sample_dataset):
    evidence = Evidence(page="https://example.com/unknown")
    finding = Finding(
        id="F-1", pipeline=Pipeline.FRESHNESS, title="Title", severity=Severity.INFO,
        trigger=Trigger(rule_id="R", type=TriggerType.DETERMINISTIC),
        evidence=evidence, suggested_action=SuggestedAction(summary="F", priority=ActionPriority.LOW)
    )
    errors = FindingValidator.validate(finding, sample_dataset)
    assert any("does not exist in CrawlDataset" in e for e in errors)

def test_11_12_13_math_consistency(sample_dataset):
    evidence = Evidence(
        pages_checked=10,
        pages_affected=15, # Invalid > 10
        affected_percentage=90.0, # Invalid != 150
        affected_pages=AffectedPages(count=12, sample=[], truncated=False) # count mismatch
    )
    finding = Finding(
        id="F-1", pipeline=Pipeline.FRESHNESS, title="Title", severity=Severity.INFO,
        trigger=Trigger(rule_id="R", type=TriggerType.DETERMINISTIC),
        evidence=evidence, suggested_action=SuggestedAction(summary="F", priority=ActionPriority.LOW)
    )
    errors = FindingValidator.validate(finding, sample_dataset)
    assert any("cannot exceed pages_checked" in e for e in errors)
    assert any("does not match computed" in e for e in errors)
    assert any("does not match pages_affected" in e for e in errors)

def test_14_truncated_sample_validation(sample_dataset):
    evidence = Evidence(
        pages_checked=10, pages_affected=10, affected_percentage=100.0,
        affected_pages=AffectedPages(count=10, sample=["https://example.com/products/a"], truncated=False) # False but length < count
    )
    finding = Finding(
        id="F-1", pipeline=Pipeline.FRESHNESS, title="Title", severity=Severity.INFO,
        trigger=Trigger(rule_id="R", type=TriggerType.DETERMINISTIC),
        evidence=evidence, suggested_action=SuggestedAction(summary="F", priority=ActionPriority.LOW)
    )
    errors = FindingValidator.validate(finding, sample_dataset)
    assert any("truncated is False but sample length is < count" in e for e in errors)

def test_15_json_serialization_success(sample_dataset):
    finding = Finding(
        id="F-1", pipeline=Pipeline.FRESHNESS, title="Title", severity=Severity.INFO,
        trigger=Trigger(rule_id="R", type=TriggerType.DETERMINISTIC),
        evidence=Evidence(page="https://example.com/products/a"), 
        suggested_action=SuggestedAction(summary="F", priority=ActionPriority.LOW)
    )
    # The validator implicitly asserts serialization during validate()
    errors = FindingValidator.validate(finding, sample_dataset)
    assert not errors
    
    # Prove the custom to_dict stringifies Enum
    d = finding.to_dict()
    assert d['pipeline'] == "freshness"
    assert d['severity'] == "info"
    json.dumps(d) # works

def test_16_non_serializable_object_rejection(sample_dataset):
    class Unserializable:
        pass
        
    finding = Finding(
        id="F-1", pipeline=Pipeline.FRESHNESS, title="Title", severity=Severity.INFO,
        trigger=Trigger(rule_id="R", type=TriggerType.DETERMINISTIC),
        evidence=Evidence(observed_value=Unserializable()), 
        suggested_action=SuggestedAction(summary="F", priority=ActionPriority.LOW)
    )
    errors = FindingValidator.validate(finding, sample_dataset)
    assert any("not JSON serializable" in e for e in errors)

def test_17_18_finding_id_determinism():
    # same rule + same normalized page -> same ID
    id1 = generate_finding_id("RULE-1", ["https://example.com/a"])
    id2 = generate_finding_id("RULE-1", ["https://example.com/a"])
    assert id1 == id2
    
    # same rule + different page -> different ID
    id3 = generate_finding_id("RULE-1", ["https://example.com/b"])
    assert id1 != id3
    
    # different rule + same page -> different ID
    id4 = generate_finding_id("RULE-2", ["https://example.com/a"])
    assert id1 != id4
    
    # same grouped signature -> same ID
    sig_1 = generate_finding_id("RULE-3", ["group_hash_X"])
    sig_2 = generate_finding_id("RULE-3", ["group_hash_X"])
    assert sig_1 == sig_2
    
    # different grouped signature -> different ID
    sig_3 = generate_finding_id("RULE-3", ["group_hash_Y"])
    assert sig_1 != sig_3
    
    # rule_id vs finding.id strictly separate
    assert "RULE-1" in id1
    assert id1.startswith("F-RULE-1-")
    assert id1 != "RULE-1"
    
    # Length test (now using 32 chars)
    assert len(id1.split("-")[-1]) == 32

def test_19_grouped_finding_representation(sample_dataset):
    evidence = Evidence(
        pages_checked=50,
        pages_affected=37,
        affected_percentage=74.0,
        affected_pages=AffectedPages(
            count=37, 
            sample=["https://example.com/products/a"], 
            truncated=True
        )
    )
    finding = Finding(
        id="F-1", pipeline=Pipeline.AI_DISCOVERABILITY, title="Grouped", severity=Severity.MEDIUM,
        trigger=Trigger(rule_id="R", type=TriggerType.DETERMINISTIC),
        evidence=evidence, suggested_action=SuggestedAction(summary="F", priority=ActionPriority.LOW)
    )
    errors = FindingValidator.validate(finding, sample_dataset)
    assert not errors

def test_21_incomplete_crawl_scope_representation(sample_dataset):
    evidence = Evidence(
        details={"crawl_complete": False, "pages_not_fetched": 1000}
    )
    finding = Finding(
        id="F-1", pipeline=Pipeline.FRESHNESS, title="Title", severity=Severity.INFO,
        trigger=Trigger(rule_id="R", type=TriggerType.DETERMINISTIC),
        evidence=evidence, suggested_action=SuggestedAction(summary="F", priority=ActionPriority.LOW)
    )
    errors = FindingValidator.validate(finding, sample_dataset)
    assert not errors

def test_22_23_optional_nlp_genai_compatibility(sample_dataset):
    finding = Finding(
        id="F-1", pipeline=Pipeline.FRESHNESS, title="Title", severity=Severity.INFO,
        trigger=Trigger(rule_id="R", type=TriggerType.DETERMINISTIC),
        evidence=Evidence(page="https://example.com/products/a"), 
        suggested_action=SuggestedAction(summary="F", priority=ActionPriority.LOW),
        nlp=NLPContext(used=True, confidence=0.9),
        genai=GenAIContext(used=True, explanation="explain")
    )
    errors = FindingValidator.validate(finding, sample_dataset)
    assert not errors
    
    # Works without them
    finding.nlp = None
    finding.genai = None
    assert not FindingValidator.validate(finding, sample_dataset)

def test_crawldataset_integration_unfetched_url(sample_dataset):
    # If the URL is only in unfetched, it's rejected for page evidence
    sample_dataset.unfetched_urls = [{"url": "https://example.com/unfetched"}]
    
    finding = Finding(
        id="F-1", pipeline=Pipeline.FRESHNESS, title="Title", severity=Severity.INFO,
        trigger=Trigger(rule_id="R", type=TriggerType.DETERMINISTIC),
        evidence=Evidence(page="https://example.com/unfetched"), 
        suggested_action=SuggestedAction(summary="F", priority=ActionPriority.LOW)
    )
    errors = FindingValidator.validate(finding, sample_dataset)
    assert any("does not exist in CrawlDataset" in e for e in errors)
