import pytest
import os
import json
from audit_shared.models.finding import Finding, Severity, Pipeline, Trigger, TriggerType, SuggestedAction, Evidence, AffectedPages, NLPContext
from audit_shared.models.data_flow import CrawlDataset, CrawlStats, CrawlDiagnostics
from audit_shared.validation.evidence_validator import ValidationResult, GroupingResult
from audit_shared.reporting.engine import ReportingEngine
from audit_shared.reporting.formatters import MarkdownFormatter, TerminalFormatter
from audit_shared.reporting.models import FinalReport
from audit_shared.reporting.scoring import calculate_score

@pytest.fixture
def sample_findings():
    f1 = Finding(
        id="F-1",
        pipeline=Pipeline.AI_DISCOVERABILITY,
        title="Missing Canonical",
        severity=Severity.HIGH,
        trigger=Trigger(rule_id="RULE-1", type=TriggerType.DETERMINISTIC),
        suggested_action=SuggestedAction(summary="Add canonical", priority=Severity.HIGH.name),
        evidence=Evidence(
            pages_checked=10,
            pages_affected=5,
            affected_pages=AffectedPages(count=5, sample=["http://ex.com/1", "http://ex.com/2"], truncated=True),
            page="http://ex.com/1",
            field="canonical",
            observed_value=None,
            expected_value="A valid URL",
            excerpt="<head>...</head>"
        )
    )
    f2 = Finding(
        id="F-2",
        pipeline=Pipeline.FRESHNESS,
        title="Stale Content",
        severity=Severity.MEDIUM,
        trigger=Trigger(rule_id="RULE-2", type=TriggerType.DETERMINISTIC),
        suggested_action=SuggestedAction(summary="Update content", priority=Severity.MEDIUM.name),
        evidence=Evidence(
            pages_checked=10,
            pages_affected=10,
            affected_pages=AffectedPages(count=10, sample=["http://ex.com/a"], truncated=False),
            page="http://ex.com/a",
            observed_value="2010-01-01"
        )
    )
    f3 = Finding(
        id="F-3",
        pipeline=Pipeline.ENGAGEMENT,
        title="NLP Semantic Match",
        severity=Severity.LOW,
        trigger=Trigger(rule_id="RULE-3", type=TriggerType.SEMANTIC),
        suggested_action=SuggestedAction(summary="Improve text", priority=Severity.LOW.name),
        evidence=Evidence(
            page="http://ex.com/b",
            excerpt="some text"
        ),
        nlp=NLPContext(
            used=True,
            semantic_evidence={
                "apparent_topic": "cats",
                "content_topic": "dogs",
                "alignment": "low"
            }
        )
    )
    return [f1, f2, f3]

@pytest.fixture
def sample_dataset():
    return CrawlDataset(
        seed_url="http://ex.com",
        crawled_at="now",
        pages=[], # not needed for engine format
        crawl_stats=CrawlStats(),
        crawl_diagnostics=CrawlDiagnostics(),
        raw_scrapy_stats={"finish_reason": "closespider_pagecount"},
        unfetched_urls=["http://ex.com/missed"] # simulates partial
    )

@pytest.fixture
def validation_result(sample_findings):
    groups = []
    for f in sample_findings:
        groups.append(GroupingResult(group_id=f.id, canonical_finding=f, source_finding_ids=[f.id], source_findings=[f]))
    return ValidationResult(total_checked=3, valid_groups=groups, invalid_groups=[], diagnostics=[])

def test_final_report_count_integrity(sample_dataset, validation_result):
    report = ReportingEngine.generate_report(sample_dataset, validation_result)
    
    # Core invariant
    assert len(report.findings) == 3
    assert report.summary.total_findings == 3
    assert report.summary.high + report.summary.medium + report.summary.low + report.summary.info == 3
    assert report.summary.high == 1
    assert report.summary.medium == 1
    assert report.summary.low == 1
    
    # Markdown formatting should have exactly the titles of the findings
    md = MarkdownFormatter.generate(report)
    md_count = md.count("### ")
    assert md_count == len(report.findings)
    
    # Terminal formatting should reflect exact numbers
    term = TerminalFormatter.generate(report)
    assert f"Findings: 3" in term
    assert f"High: 1" in term
    assert f"Medium: 1" in term
    
    # JSON serialization
    json_str = json.dumps(report.to_dict())
    rehydrated = json.loads(json_str)
    assert len(rehydrated["findings"]) == len(report.findings)
    assert rehydrated["summary"]["total_findings"] == report.summary.total_findings

def test_score_logic():
    f1 = Finding(id="1", pipeline=Pipeline.FRESHNESS, title="T", severity=Severity.HIGH, trigger=Trigger("1", TriggerType.DETERMINISTIC), suggested_action=SuggestedAction("s", "HIGH"), evidence=Evidence())
    f2 = Finding(id="2", pipeline=Pipeline.FRESHNESS, title="T", severity=Severity.MEDIUM, trigger=Trigger("1", TriggerType.DETERMINISTIC), suggested_action=SuggestedAction("s", "HIGH"), evidence=Evidence())
    
    # 100 - 20 - 10 = 70
    assert calculate_score([f1, f2]) == 70
    
    # test bounds
    f3 = Finding(id="3", pipeline=Pipeline.FRESHNESS, title="T", severity=Severity.HIGH, trigger=Trigger("1", TriggerType.DETERMINISTIC), suggested_action=SuggestedAction("s", "HIGH"), evidence=Evidence())
    many = [f3] * 10 
    assert calculate_score(many) == 0 # 100 - 200 = -100 bounded to 0
    
    # test zero
    assert calculate_score([]) == 100

def test_evidence_rendering(sample_dataset, validation_result):
    report = ReportingEngine.generate_report(sample_dataset, validation_result)
    md = MarkdownFormatter.generate(report)
    
    # Should show missing field safely without 'None' if we omitted it
    # But wait, we DID pass `observed_value=None` in F1. 
    # Our formatter says `if f.evidence.observed_value is not None:`
    assert "Observed value:" not in md.split("### Missing Canonical")[1].split("###")[0]
    
    # Truncated sample text
    assert "5 pages affected. Sample shown:" in md
    
    # Non truncated text
    assert "10 pages affected. List:" in md
    
    # Semantic text
    assert "**Apparent topic:** cats" in md
    assert "**Content topic:** dogs" in md

def test_partial_crawl_wording(validation_result):
    ds1 = CrawlDataset(seed_url="http://x", crawled_at="", pages=[], crawl_stats=CrawlStats(), crawl_diagnostics=CrawlDiagnostics(), unfetched_urls=[], raw_scrapy_stats={})
    report1 = ReportingEngine.generate_report(ds1, validation_result)
    assert report1.crawl.status == "Complete"
    
    ds2 = CrawlDataset(seed_url="http://x", crawled_at="", pages=[], crawl_stats=CrawlStats(), crawl_diagnostics=CrawlDiagnostics(), unfetched_urls=["http://x/1"], raw_scrapy_stats={"finish_reason": "closespider_pagecount"})
    report2 = ReportingEngine.generate_report(ds2, validation_result)
    assert "Partial" in report2.crawl.status
    assert "limit reached" in report2.crawl.status

def test_markdown_escaping(sample_dataset):
    f = Finding(
        id="F-mal",
        pipeline=Pipeline.FRESHNESS,
        title="<script>alert(1)</script>",
        severity=Severity.INFO,
        trigger=Trigger(rule_id="1", type=TriggerType.DETERMINISTIC),
        suggested_action=SuggestedAction(summary="`rm -rf`", priority="LOW"),
        evidence=Evidence(
            page="<url>"
        )
    )
    vr = ValidationResult(total_checked=1, valid_groups=[GroupingResult(group_id="G1", canonical_finding=f, source_finding_ids=[], source_findings=[])], invalid_groups=[], diagnostics=[])
    report = ReportingEngine.generate_report(sample_dataset, vr)
    md = MarkdownFormatter.generate(report)
    
    assert "<script>" not in md
    assert "&lt;script&gt;" in md
    assert "&lt;url&gt;" in md
    assert "`rm" not in md
    assert "'rm" in md # escaped backtick
