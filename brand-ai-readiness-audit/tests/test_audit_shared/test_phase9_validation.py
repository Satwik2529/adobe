import pytest
from audit_shared.models.finding import Finding, Pipeline, Severity, Trigger, TriggerType, SuggestedAction, ActionPriority, Evidence, generate_finding_id, AffectedPages
from audit_shared.models.grouping import EvaluationScope, GroupingResult
from audit_shared.validation.evidence_validator import EvidenceValidator
from audit_shared.models.data_flow import CrawlDataset, PageRecord, ExtractedData
import copy

def make_finding(url, rule_id="AI-CANONICAL-001", obs_val="No canonical tag found", trigger_type=TriggerType.DETERMINISTIC, field="canonical", source="extracted", title="Test", excerpt=None, details=None):
    return Finding(
        id=generate_finding_id(rule_id, [url]),
        pipeline=Pipeline.AI_DISCOVERABILITY,
        title=title,
        severity=Severity.MEDIUM,
        trigger=Trigger(rule_id=rule_id, type=trigger_type),
        suggested_action=SuggestedAction(summary="Test Action", priority=ActionPriority.MEDIUM),
        evidence=Evidence(
            page=url,
            source=source,
            field=field,
            observed_value=obs_val,
            excerpt=excerpt,
            details=details or {},
            pages_checked=1,
            pages_affected=1,
            affected_percentage=100.0,
            affected_pages=AffectedPages(count=1, sample=[url], truncated=False)
        )
    )

def get_scope():
    return EvaluationScope(
        html_pages_crawled=10,
        successful_pages=10,
        total_pages_evaluated=10,
        is_truncated=False
    )

def make_group(findings, scope):
    # Mocking group creation for testing validator
    rep = findings[0]
    unique_urls = sorted(list(set(f.evidence.page for f in findings if f.evidence and f.evidence.page)))
    canonical = copy.deepcopy(rep)
    if canonical.evidence:
        canonical.evidence.pages_checked = scope.total_pages_evaluated
        canonical.evidence.pages_affected = len(unique_urls)
        canonical.evidence.affected_percentage = (len(unique_urls) / scope.total_pages_evaluated) * 100
        canonical.evidence.affected_pages = AffectedPages(count=len(unique_urls), sample=unique_urls[:10], truncated=len(unique_urls) > 10)
    
    return GroupingResult(
        group_id=f"G-{rep.trigger.rule_id}-TEST",
        canonical_finding=canonical,
        source_finding_ids=[f.id for f in findings],
        source_findings=findings
    )

def get_dataset():
    p1 = PageRecord(url="https://example.com/a", final_url="https://example.com/a", status_code=200, content_type="text/html", depth=1, parent_url=None)
    p1.extracted = ExtractedData(title="Title A", visible_text="Some text here.")
    
    p2 = PageRecord(url="https://example.com/b", final_url="https://example.com/b", status_code=200, content_type="text/html", depth=1, parent_url=None)
    p2.extracted = ExtractedData(title="Title B", canonical="https://example.com/b")
    
    p3 = PageRecord(url="https://example.com/c", final_url="https://example.com/c", status_code=404, content_type="text/html", depth=1, parent_url=None)
    p3.extracted = ExtractedData(detailed_internal_links=[{"url": "https://example.com/broken", "text": "click"}])
    
    return CrawlDataset(
        seed_url="https://example.com",
        crawled_at="",
        pages=[p1, p2, p3],
        unfetched_urls=["https://example.com/unfetched"]
    )

def test_every_source_finding_provenance_validated():
    ds = get_dataset()
    scope = get_scope()
    
    # 9 valid, 1 invalid (unfetched)
    findings = [make_finding(f"https://example.com/a", title=f"Test {i}") for i in range(9)]
    findings.append(make_finding("https://example.com/unfetched", title="Test 9"))
    
    group = make_group(findings, scope)
    res = EvidenceValidator.validate_all([group], ds, scope)
    
    assert len(res.valid_groups) == 0
    assert len(res.invalid_groups) == 1
    diag = res.diagnostics[0]
    assert any("unfetched_urls" in err for err in diag.errors)

def test_one_invalid_source_invalidates_group():
    ds = get_dataset()
    scope = get_scope()
    
    findings = [
        make_finding("https://example.com/a"),
        make_finding("https://example.com/not-in-dataset")
    ]
    group = make_group(findings, scope)
    res = EvidenceValidator.validate_all([group], ds, scope)
    assert len(res.invalid_groups) == 1
    assert any("not found in crawled dataset" in err for err in res.diagnostics[0].errors)

def test_observed_value_matches_crawldataset():
    ds = get_dataset()
    scope = get_scope()
    
    # Page A has no canonical.
    f = make_finding("https://example.com/a", rule_id="AI-CANONICAL-001")
    group = make_group([f], scope)
    res = EvidenceValidator.validate_all([group], ds, scope)
    assert len(res.valid_groups) == 1

def test_observed_value_mismatch_rejected():
    ds = get_dataset()
    scope = get_scope()
    
    # Page B has canonical, but rule says it doesn't.
    f = make_finding("https://example.com/b", rule_id="AI-CANONICAL-001")
    group = make_group([f], scope)
    res = EvidenceValidator.validate_all([group], ds, scope)
    assert len(res.invalid_groups) == 1
    assert any("Value mismatch" in err for err in res.diagnostics[0].errors)

def test_derived_evidence_validation():
    ds = get_dataset()
    scope = get_scope()
    
    # Page C has a link to broken.
    f = make_finding("https://example.com/c", rule_id="AI-LINK-001", obs_val="broken link https://example.com/broken", field="internal_links")
    group = make_group([f], scope)
    res = EvidenceValidator.validate_all([group], ds, scope)
    assert len(res.valid_groups) == 1

def test_explicit_scope_denominator():
    ds = get_dataset()
    scope = get_scope()
    
    f = make_finding("https://example.com/a")
    group = make_group([f], scope)
    
    # Tamper with scope match
    group.canonical_finding.evidence.pages_checked = 999 
    res = EvidenceValidator.validate_all([group], ds, scope)
    assert len(res.invalid_groups) == 1
    assert any("pages_checked (999) does not match explicit EvaluationScope (10)" in err for err in res.diagnostics[0].errors)

def test_semantic_supporting_text_provenance():
    ds = get_dataset()
    scope = get_scope()
    
    f1 = make_finding("https://example.com/a", rule_id="SEM-001", trigger_type=TriggerType.SEMANTIC, excerpt="text here", details={"confidence": 0.9})
    group1 = make_group([f1], scope)
    res1 = EvidenceValidator.validate_all([group1], ds, scope)
    assert len(res1.valid_groups) == 1
    
    f2 = make_finding("https://example.com/a", rule_id="SEM-001", trigger_type=TriggerType.SEMANTIC, excerpt="Not in page", details={"confidence": 0.9})
    group2 = make_group([f2], scope)
    res2 = EvidenceValidator.validate_all([group2], ds, scope)
    assert len(res2.invalid_groups) == 1
    assert any("Semantic excerpt not found" in err for err in res2.diagnostics[0].errors)

def test_missing_evidence():
    ds = get_dataset()
    scope = get_scope()
    
    f = make_finding("https://example.com/a")
    f.evidence = None
    group = make_group([f], scope)
    res = EvidenceValidator.validate_all([group], ds, scope)
    assert len(res.invalid_groups) == 1

def test_incorrect_affected_count():
    ds = get_dataset()
    scope = get_scope()
    
    f = make_finding("https://example.com/a")
    group = make_group([f], scope)
    group.canonical_finding.evidence.affected_pages.count = 999
    res = EvidenceValidator.validate_all([group], ds, scope)
    assert len(res.invalid_groups) == 1

def test_invalid_url():
    ds = get_dataset()
    scope = get_scope()
    
    f = make_finding("not-a-url")
    group = make_group([f], scope)
    res = EvidenceValidator.validate_all([group], ds, scope)
    assert len(res.invalid_groups) == 1

def test_duplicate_sample_urls():
    ds = get_dataset()
    scope = get_scope()
    
    f = make_finding("https://example.com/a")
    group = make_group([f], scope)
    group.canonical_finding.evidence.affected_pages.sample = ["https://example.com/a", "https://example.com/a"]
    res = EvidenceValidator.validate_all([group], ds, scope)
    assert len(res.invalid_groups) == 1
    assert any("duplicate URLs" in err for err in res.diagnostics[0].errors)

def test_grouped_finding_validation():
    ds = get_dataset()
    scope = get_scope()
    
    # Use two pages that BOTH have NO canonical, to pass the deep validation for AI-CANONICAL-001.
    p4 = PageRecord(url="https://example.com/d", final_url="https://example.com/d", status_code=200, content_type="text/html", depth=1, parent_url=None)
    p4.extracted = ExtractedData(title="Title D")
    ds.pages.append(p4)
    
    findings = [make_finding("https://example.com/a"), make_finding("https://example.com/d")]
    group = make_group(findings, scope)
    res = EvidenceValidator.validate_all([group], ds, scope)
    assert len(res.valid_groups) == 1
    # Check source findings preservation
    assert len(res.valid_groups[0].source_findings) == 2
