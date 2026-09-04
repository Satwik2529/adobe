import pytest
from typing import List
from audit_shared.models.finding import (
    Finding, Pipeline, Severity, Trigger, TriggerType, SuggestedAction, ActionPriority, Evidence, generate_finding_id
)
from audit_shared.models.data_flow import CrawlDataset, CrawlStats, CrawlDiagnostics, PageRecord
from audit_shared.rules.base import AuditRule
from audit_shared.rules.registry import RuleRegistry
from audit_shared.rules.engine import RuleEngine
from audit_shared.rules.models import RuleExecutionStatus

# Dummy Rules for testing
class DummyRuleNoFindings(AuditRule):
    @property
    def rule_id(self) -> str: return "TEST-001-NONE"
    @property
    def pipeline(self) -> Pipeline: return Pipeline.AI_DISCOVERABILITY
    @property
    def description(self) -> str: return "Produces no findings"
    def evaluate(self, dataset: CrawlDataset) -> List[Finding]:
        return []

class DummyRuleOneFinding(AuditRule):
    @property
    def rule_id(self) -> str: return "TEST-002-ONE"
    @property
    def pipeline(self) -> Pipeline: return Pipeline.FRESHNESS
    @property
    def description(self) -> str: return "Produces one valid finding"
    def evaluate(self, dataset: CrawlDataset) -> List[Finding]:
        url = dataset.pages[0].url if dataset.pages else "https://example.com"
        return [
            Finding(
                id=generate_finding_id(self.rule_id, [url]),
                pipeline=self.pipeline,
                title="Test Finding",
                severity=Severity.HIGH,
                trigger=Trigger(rule_id=self.rule_id, type=TriggerType.DETERMINISTIC),
                suggested_action=SuggestedAction(summary="Fix", priority=ActionPriority.HIGH),
                evidence=Evidence(
                    page=url, source="test", field="none", observed_value="", pages_checked=1, pages_affected=1, affected_percentage=100.0
                )
            )
        ]

class DummyRuleMultipleFindings(AuditRule):
    @property
    def rule_id(self) -> str: return "TEST-003-MULTIPLE"
    @property
    def pipeline(self) -> Pipeline: return Pipeline.ENGAGEMENT
    @property
    def description(self) -> str: return "Produces multiple valid findings"
    def evaluate(self, dataset: CrawlDataset) -> List[Finding]:
        url1 = dataset.pages[0].url if dataset.pages else "https://example.com/1"
        url2 = dataset.pages[1].url if len(dataset.pages) > 1 else "https://example.com/2"
        return [
            Finding(
                id=generate_finding_id(self.rule_id, [url1]), pipeline=self.pipeline, title="F1", severity=Severity.MEDIUM,
                trigger=Trigger(rule_id=self.rule_id, type=TriggerType.DETERMINISTIC),
                suggested_action=SuggestedAction(summary="Fix", priority=ActionPriority.MEDIUM),
                evidence=Evidence(page=url1, source="test", field="x", observed_value="y", pages_checked=2, pages_affected=1, affected_percentage=50.0)
            ),
            Finding(
                id=generate_finding_id(self.rule_id, [url2]), pipeline=self.pipeline, title="F2", severity=Severity.LOW,
                trigger=Trigger(rule_id=self.rule_id, type=TriggerType.DETERMINISTIC),
                suggested_action=SuggestedAction(summary="Fix", priority=ActionPriority.LOW),
                evidence=Evidence(page=url2, source="test", field="x", observed_value="z", pages_checked=2, pages_affected=1, affected_percentage=50.0)
            )
        ]

class DummyRuleException(AuditRule):
    @property
    def rule_id(self) -> str: return "TEST-004-ERROR"
    @property
    def pipeline(self) -> Pipeline: return Pipeline.AI_DISCOVERABILITY
    @property
    def description(self) -> str: return "Throws an exception"
    def evaluate(self, dataset: CrawlDataset) -> List[Finding]:
        raise ValueError("Simulated rule failure")

class DummyRuleInvalidFinding(AuditRule):
    @property
    def rule_id(self) -> str: return "TEST-005-INVALID"
    @property
    def pipeline(self) -> Pipeline: return Pipeline.AI_DISCOVERABILITY
    @property
    def description(self) -> str: return "Produces invalid finding (unfetched URL)"
    def evaluate(self, dataset: CrawlDataset) -> List[Finding]:
        return [
            Finding(
                id=generate_finding_id(self.rule_id, ["https://never-fetched.com"]),
                pipeline=self.pipeline, title="Bad", severity=Severity.LOW,
                trigger=Trigger(rule_id=self.rule_id, type=TriggerType.DETERMINISTIC),
                suggested_action=SuggestedAction(summary="Fix", priority=ActionPriority.LOW),
                evidence=Evidence(page="https://never-fetched.com", source="test", field="none", observed_value="", pages_checked=1, pages_affected=1, affected_percentage=100.0)
            )
        ]

@pytest.fixture
def sample_dataset():
    return CrawlDataset(
        seed_url="https://example.com", crawled_at="2026-09-04T00:00:00Z",
        pages=[
            PageRecord(url="https://example.com/1", final_url="https://example.com/1", status_code=200, content_type="text/html", depth=1, parent_url=None),
            PageRecord(url="https://example.com/2", final_url="https://example.com/2", status_code=200, content_type="text/html", depth=1, parent_url=None)
        ],
        crawl_stats=CrawlStats(urls_discovered=2, urls_scheduled=2, requests_attempted=2, responses_received=2, html_pages_crawled=2, successful_pages=2, failed_pages=0, robots_blocked=0, duplicate_urls=0, redirects=0, non_html_responses=0, crawl_duration=1.0),
        crawl_diagnostics=CrawlDiagnostics(robots_txt_fetched=True, robots_txt_status=200, crawl_errors=[], request_failures=0, extraction_failures=0, pages_discovered_not_fetched=0, robots_blocked_urls=0, crawl_termination_reason="finished", configured_depth_limit=10, configured_page_limit=100),
        raw_scrapy_stats={}, unfetched_urls=[]
    )

def test_registry_valid_registration():
    registry = RuleRegistry()
    registry.register(DummyRuleNoFindings())
    assert len(registry.list()) == 1

def test_registry_duplicate_rejection():
    registry = RuleRegistry()
    registry.register(DummyRuleNoFindings())
    with pytest.raises(ValueError, match="already registered"):
        registry.register(DummyRuleNoFindings())

def test_registry_invalid_rule_rejection():
    registry = RuleRegistry()
    with pytest.raises(TypeError, match="must inherit from AuditRule"):
        registry.register(object()) # type: ignore

def test_deterministic_ordering():
    registry = RuleRegistry()
    # Insert in arbitrary order
    registry.register(DummyRuleMultipleFindings()) # TEST-003
    registry.register(DummyRuleNoFindings())       # TEST-001
    registry.register(DummyRuleOneFinding())       # TEST-002
    
    rules = registry.get_all()
    assert [r.rule_id for r in rules] == ["TEST-001-NONE", "TEST-002-ONE", "TEST-003-MULTIPLE"]

def test_pipeline_filtering():
    registry = RuleRegistry()
    registry.register(DummyRuleNoFindings())       # AI_DISCOVERABILITY
    registry.register(DummyRuleOneFinding())       # FRESHNESS
    registry.register(DummyRuleMultipleFindings()) # ENGAGEMENT
    
    ai_rules = registry.get_all(Pipeline.AI_DISCOVERABILITY)
    assert len(ai_rules) == 1
    assert ai_rules[0].rule_id == "TEST-001-NONE"
    
    fresh_rules = registry.get_all(Pipeline.FRESHNESS)
    assert len(fresh_rules) == 1
    assert fresh_rules[0].rule_id == "TEST-002-ONE"

def test_engine_zero_findings(sample_dataset):
    registry = RuleRegistry()
    registry.register(DummyRuleNoFindings())
    
    result = RuleEngine.run(sample_dataset, registry)
    assert result.total_rules_run == 1
    assert result.successful_rules == 1
    assert result.failed_rules == 0
    assert len(result.findings) == 0
    assert result.diagnostics[0].status == RuleExecutionStatus.NO_FINDINGS
    assert result.diagnostics[0].findings_generated == 0

def test_engine_one_finding(sample_dataset):
    registry = RuleRegistry()
    registry.register(DummyRuleOneFinding())
    
    result = RuleEngine.run(sample_dataset, registry)
    assert result.total_rules_run == 1
    assert result.successful_rules == 1
    assert len(result.findings) == 1
    assert result.diagnostics[0].status == RuleExecutionStatus.SUCCESS
    assert result.diagnostics[0].findings_generated == 1
    assert result.diagnostics[0].valid_findings == 1

def test_engine_multiple_findings(sample_dataset):
    registry = RuleRegistry()
    registry.register(DummyRuleMultipleFindings())
    
    result = RuleEngine.run(sample_dataset, registry)
    assert len(result.findings) == 2
    # Check no grouping/deduplication was silently applied
    assert result.findings[0].id != result.findings[1].id

def test_engine_exception_isolation(sample_dataset):
    registry = RuleRegistry()
    registry.register(DummyRuleOneFinding())       # TEST-002 (Success)
    registry.register(DummyRuleException())        # TEST-004 (Exception)
    
    result = RuleEngine.run(sample_dataset, registry)
    
    assert result.total_rules_run == 2
    assert result.successful_rules == 1
    assert result.failed_rules == 1
    assert len(result.findings) == 1 # Valid finding from TEST-002 survived
    
    # Check diagnostic for failed rule
    failed_diag = next(d for d in result.diagnostics if d.rule_id == "TEST-004-ERROR")
    assert failed_diag.status == RuleExecutionStatus.FAILED
    assert failed_diag.error_type == "ValueError"
    assert failed_diag.error_message == "Simulated rule failure"
    assert "Traceback" in failed_diag.traceback

def test_engine_invalid_finding_rejection(sample_dataset):
    registry = RuleRegistry()
    registry.register(DummyRuleInvalidFinding())
    
    result = RuleEngine.run(sample_dataset, registry)
    
    assert result.total_rules_run == 1
    assert result.successful_rules == 0
    assert result.failed_rules == 1
    assert len(result.findings) == 0 # Invalid finding is dropped
    
    diag = result.diagnostics[0]
    assert diag.status == RuleExecutionStatus.INVALID_FINDINGS
    assert diag.findings_generated == 1
    assert diag.valid_findings == 0
    assert diag.invalid_findings == 1
    assert len(diag.validation_errors) > 0
    assert "https://never-fetched.com" in diag.validation_errors[0]

def test_engine_deterministic_execution_ids(sample_dataset):
    registry = RuleRegistry()
    registry.register(DummyRuleOneFinding())
    
    res1 = RuleEngine.run(sample_dataset, registry)
    res2 = RuleEngine.run(sample_dataset, registry)
    
    assert res1.findings[0].id == res2.findings[0].id
