import pytest
from audit_shared.models.finding import Finding, Pipeline, Severity, Trigger, TriggerType, SuggestedAction, ActionPriority, Evidence, generate_finding_id
from audit_shared.models.grouping import EvaluationScope, GroupingResult
from audit_shared.grouping.deduplicator import GroupDeduplicator
from audit_shared.validation.finding_validator import FindingValidator
from audit_shared.models.data_flow import CrawlDataset, PageRecord

def make_finding(url, rule_id="AI-TEST-001", severity=Severity.MEDIUM, title="Test Mechanism", obs_val="val", trigger_type=TriggerType.DETERMINISTIC):
    return Finding(
        id=generate_finding_id(rule_id, [url]),
        pipeline=Pipeline.AI_DISCOVERABILITY,
        title=title,
        severity=severity,
        trigger=Trigger(rule_id=rule_id, type=trigger_type),
        suggested_action=SuggestedAction(summary="Test Action", priority=ActionPriority.MEDIUM),
        evidence=Evidence(
            page=url,
            source="test",
            field="test_field",
            observed_value=obs_val
        )
    )

def get_scope():
    return EvaluationScope(
        html_pages_crawled=50,
        successful_pages=50,
        total_pages_evaluated=50,
        is_truncated=False
    )

def test_evaluation_scope_independence():
    findings = [
        make_finding("https://example.com/a"),
        make_finding("https://example.com/b")
    ]
    scope = get_scope()
    scope.total_pages_evaluated = 100
    
    results = GroupDeduplicator.process(findings, scope)
    assert len(results) == 1
    canonical = results[0].canonical_finding
    assert canonical.evidence.pages_checked == 100
    assert canonical.evidence.pages_affected == 2
    assert canonical.evidence.affected_percentage == 2.0

def test_partial_crawl_claims():
    findings = [make_finding("https://example.com/a")]
    scope = EvaluationScope(
        html_pages_crawled=5,
        successful_pages=5,
        total_pages_evaluated=5,
        is_truncated=True
    )
    
    results = GroupDeduplicator.process(findings, scope)
    canonical = results[0].canonical_finding
    assert canonical.evidence.pages_checked == 5
    assert canonical.evidence.pages_affected == 1
    assert canonical.evidence.affected_percentage == 20.0
    # The wording isn't site-wide because pages_checked is clearly 5.

def test_source_evidence_isolation():
    findings = [make_finding("https://example.com/a")]
    results = GroupDeduplicator.process(findings, get_scope())
    canonical = results[0].canonical_finding
    # Full findings shouldn't be duplicated in evidence.details
    assert "source_findings" not in canonical.evidence.details
    # Instead they are in the result object
    assert len(results[0].source_findings) == 1

def test_severity_conflicts():
    f1 = make_finding("https://example.com/a", severity=Severity.MEDIUM)
    f2 = make_finding("https://example.com/b", severity=Severity.HIGH)
    
    # Same mechanism, different severities should separate into distinct groups
    results = GroupDeduplicator.process([f1, f2], get_scope())
    assert len(results) == 2
    severities = {r.canonical_finding.severity for r in results}
    assert severities == {Severity.MEDIUM, Severity.HIGH}

def test_mechanism_separation():
    f1 = make_finding("https://example.com/a", rule_id="RULE-1")
    f2 = make_finding("https://example.com/a", rule_id="RULE-2")
    
    results = GroupDeduplicator.process([f1, f2], get_scope())
    assert len(results) == 2

def test_semantic_separation():
    f1 = make_finding("https://example.com/a", trigger_type=TriggerType.DETERMINISTIC)
    f2 = make_finding("https://example.com/b", trigger_type=TriggerType.SEMANTIC)
    
    results = GroupDeduplicator.process([f1, f2], get_scope())
    assert len(results) == 2

def test_deterministic_sampling():
    urls = [f"https://example.com/{i}" for i in range(15)]
    # Shuffle URLs to ensure sampling handles it deterministically
    import random
    random.seed(42)
    shuffled_urls = list(urls)
    random.shuffle(shuffled_urls)
    
    findings = [make_finding(url) for url in shuffled_urls]
    results = GroupDeduplicator.process(findings, get_scope())
    
    canonical = results[0].canonical_finding
    assert canonical.evidence.affected_pages.count == 15
    assert canonical.evidence.affected_pages.truncated is True
    assert len(canonical.evidence.affected_pages.sample) == 10
    
    # Expected sorted order: 0, 1, 10, 11, 12, 13, 14, 2, 3, 4
    expected_sample = sorted(urls)[:10]
    assert canonical.evidence.affected_pages.sample == expected_sample

def test_full_evidence_retrievable():
    findings = [
        make_finding("https://example.com/a", obs_val="obs1"),
        make_finding("https://example.com/b", obs_val="obs2")
    ]
    results = GroupDeduplicator.process(findings, get_scope())
    
    source = results[0].source_findings
    assert len(source) == 2
    obs_vals = {f.evidence.observed_value for f in source}
    assert obs_vals == {"obs1", "obs2"}

def test_exact_duplicate_removal():
    f1 = make_finding("https://example.com/a", obs_val="obs1")
    f2 = make_finding("https://example.com/a", obs_val="obs1") # exact dup
    f3 = make_finding("https://example.com/b", obs_val="obs2") # different page
    
    results = GroupDeduplicator.process([f1, f2, f3], get_scope())
    assert len(results) == 1
    # 2 unique pages affected
    assert results[0].canonical_finding.evidence.pages_affected == 2
    assert len(results[0].source_findings) == 2 # The exact dup was stripped before grouping

def test_finding_validator_compatibility():
    findings = [make_finding("https://example.com/a"), make_finding("https://example.com/b")]
    results = GroupDeduplicator.process(findings, get_scope())
    
    canonical = results[0].canonical_finding
    dataset = CrawlDataset(
        seed_url="https://example.com",
        crawled_at="",
        pages=[PageRecord(url="https://example.com/a", final_url="https://example.com/a", status_code=200, content_type="text/html", depth=1, parent_url=None),
               PageRecord(url="https://example.com/b", final_url="https://example.com/b", status_code=200, content_type="text/html", depth=1, parent_url=None)]
    )
    
    errors = FindingValidator.validate(canonical, dataset)
    assert len(errors) == 0

def test_grouping_affected_percentage():
    # Write a test proving that 2 duplicate findings out of a 10-page site yields pages_affected=2 and affected_percentage=20.0
    findings = [
        make_finding("https://example.com/page1", "ISSUE-1"),
        make_finding("https://example.com/page2", "ISSUE-1")
    ]
    # scope with 10 total pages
    scope = EvaluationScope(
        html_pages_crawled=10,
        successful_pages=10,
        total_pages_evaluated=10,
        is_truncated=False
    )
    results = GroupDeduplicator.process(findings, scope)
    assert len(results) == 1
    
    canonical = results[0].canonical_finding
    assert canonical.evidence.pages_affected == 2
    assert canonical.evidence.affected_percentage == 20.0

def test_grouping_percentage_cap():
    # If pages_affected > total_pages_evaluated (e.g. edge case), cap at 100
    findings = [make_finding(f"https://example.com/page{i}", "ISSUE-1") for i in range(5)]
    scope = EvaluationScope(
        html_pages_crawled=3,
        successful_pages=3,
        total_pages_evaluated=3,
        is_truncated=False
    )
    results = GroupDeduplicator.process(findings, scope)
    assert len(results) == 1
    assert results[0].canonical_finding.evidence.affected_percentage == 100.0

def test_finding_validator_hallucinated_sample():
    findings = [make_finding("https://example.com/a")]
    scope = EvaluationScope(
        html_pages_crawled=1,
        successful_pages=1,
        total_pages_evaluated=1,
        is_truncated=False
    )
    results = GroupDeduplicator.process(findings, scope)
    
    canonical = results[0].canonical_finding
    # Inject a hallucinated URL into the sample
    canonical.evidence.affected_pages.sample.append("https://example.com/hallucinated")
    
    dataset = CrawlDataset(
        seed_url="https://example.com",
        crawled_at="",
        pages=[PageRecord(url="https://example.com/a", final_url="https://example.com/a", status_code=200, content_type="text/html", depth=1, parent_url=None)]
    )
    
    errors = FindingValidator.validate(canonical, dataset)
    assert len(errors) > 0
    assert any("does not exist in CrawlDataset" in e and "hallucinated" in e for e in errors)

def test_deterministic_repetition():
    urls = [f"https://example.com/{i}" for i in range(5)]
    f1 = [make_finding(url) for url in urls]
    f2 = [make_finding(url) for url in reversed(urls)]
    
    r1 = GroupDeduplicator.process(f1, get_scope())
    r2 = GroupDeduplicator.process(f2, get_scope())
    
    assert r1[0].group_id == r2[0].group_id
    assert r1[0].canonical_finding.evidence.affected_pages.sample == r2[0].canonical_finding.evidence.affected_pages.sample

def test_acceptance_controlled_fixture():
    # 37 equivalent page findings
    urls = [f"https://example.com/page_{i}" for i in range(37)]
    findings = [make_finding(u) for u in urls]
    
    scope = EvaluationScope(
        html_pages_crawled=50,
        successful_pages=50,
        total_pages_evaluated=50,
        is_truncated=False
    )
    
    results = GroupDeduplicator.process(findings, scope)
    
    # -> 1 grouped finding
    assert len(results) == 1
    result = results[0]
    
    # -> 37 source_finding_ids
    assert len(result.source_finding_ids) == 37
    
    # -> 37 unique affected URLs
    assert result.canonical_finding.evidence.pages_affected == 37
    assert result.canonical_finding.evidence.affected_pages.count == 37
    
    # -> deterministic sample
    expected_sample = sorted(urls)[:10]
    assert result.canonical_finding.evidence.affected_pages.sample == expected_sample
    
    # -> deterministic group ID
    assert result.group_id.startswith("G-AI-TEST-001-")
    
    # -> correct EvaluationScope denominator
    assert result.canonical_finding.evidence.pages_checked == 50
    assert result.canonical_finding.evidence.affected_percentage == (37/50)*100
    
    # -> complete internal source evidence
    assert len(result.source_findings) == 37
    
    # -> validator passes
    dataset = CrawlDataset(
        seed_url="https://example.com",
        crawled_at="",
        pages=[PageRecord(url=u, final_url=u, status_code=200, content_type="text/html", depth=1, parent_url=None) for u in urls]
    )
    errors = FindingValidator.validate(result.canonical_finding, dataset)
    assert len(errors) == 0

