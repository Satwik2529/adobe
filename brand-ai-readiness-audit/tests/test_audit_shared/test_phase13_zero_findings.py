import pytest
import asyncio

from audit_shared.rules.registry import RuleRegistry
from audit_shared.rules.ai_discoverability import register_ai_discoverability_rules
from audit_shared.rules.engine import RuleEngine
from audit_shared.models.data_flow import CrawlDataset, PageRecord, CrawlStats, ExtractedData, CrawlDiagnostics
from audit_shared.grouping.deduplicator import GroupDeduplicator
from audit_shared.validation.evidence_validator import EvidenceValidator
from audit_shared.models.grouping import EvaluationScope
from audit_shared.genai.client import GenAIClient
from audit_shared.genai.engine import GenAIEngine
from audit_shared.reporting.engine import ReportingEngine

def test_zero_findings_semantics():
    dataset = CrawlDataset(
        seed_url="https://perfect-site.com",
        crawled_at="2024-01-01T00:00:00Z",
        crawl_stats=CrawlStats(
            urls_discovered=1, urls_scheduled=1, requests_attempted=1, responses_received=1,
            html_pages_crawled=1, successful_pages=1, failed_pages=0, robots_blocked=0,
            duplicate_urls=0, redirects=0, non_html_responses=0, crawl_duration=1.0
        ),
        crawl_diagnostics=CrawlDiagnostics(robots_txt_fetched=True),
        pages=[
            PageRecord(
                url="https://perfect-site.com",
                final_url="https://perfect-site.com",
                status_code=200,
                content_type="text/html",
                depth=0,
                parent_url=None,
                crawl_status="success",
                extracted=ExtractedData(
                    title="Perfect Site",
                    meta_robots=["index", "follow"],
                    meta_description="This is a perfect site description.",
                    h1s=["Perfect Site H1"],
                    canonical="https://perfect-site.com",
                    language="en",
                    page_type="article",
                    visible_text="This is a perfect site with lots of content."
                )
            )
        ]
    )

    # 1. Rule Engine
    registry = RuleRegistry()
    register_ai_discoverability_rules(registry)
    
    result = RuleEngine.run(dataset, registry)
    raw_findings = result.findings
    assert len(raw_findings) == 0  # Perfect site!
    
    # 2. Grouping
    scope = EvaluationScope(
        html_pages_crawled=1, successful_pages=1, total_pages_evaluated=1, is_truncated=False
    )
    groups = GroupDeduplicator.process(raw_findings, scope)
    assert len(groups) == 0
    
    # 3. Validation
    from audit_shared.validation.evidence_validator import EvidenceValidator
    val_result = EvidenceValidator.validate_all(groups, dataset, scope)
    assert len(val_result.valid_groups) == 0
    
    # 4. GenAI (Should not attempt requests for 0 groups)
    genai_client = GenAIClient(use_mock=True)
    genai_engine = GenAIEngine(client=genai_client)
    genai_diagnostics = asyncio.run(genai_engine.enrich_groups(val_result.valid_groups))
    assert genai_diagnostics.requests_attempted == 0
    
    # 5. Reporting
    report = ReportingEngine.generate_report(dataset, val_result)
    report.diagnostics.genai = genai_diagnostics
    
    # Assert zero-finding semantics
    assert report.summary.score == 100
    assert report.summary.total_findings == 0
    assert report.evaluation_scope.pages_evaluated == 1 # Not zero!
    assert report.diagnostics.genai.requests_attempted == 0
