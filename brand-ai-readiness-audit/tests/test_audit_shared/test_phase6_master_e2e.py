import pytest
import json
import asyncio
from typing import Dict, Any

from tests.crawler.fixture_server import start_server
from audit_shared.config.settings import CrawlSettings
from audit_shared.crawl.runner import run_crawl
from audit_shared.rules.registry import RuleRegistry
from audit_shared.rules.ai_discoverability import register_ai_discoverability_rules
from audit_shared.rules.freshness import register_freshness_rules
from audit_shared.rules.engagement import register_engagement_rules
from audit_shared.rules.engine import RuleEngine
from audit_shared.models.data_flow import CrawlDataset, ExtractedData, PageRecord, DateCandidate, ExtractionDiagnostics, CrawlStats, CrawlDiagnostics
from audit_shared.nlp.client import NLPClient
from audit_shared.nlp.rules import SemanticTopicRule
from audit_shared.nlp.interpreter import SemanticInterpreter
from audit_shared.grouping.deduplicator import GroupDeduplicator
from audit_shared.models.grouping import EvaluationScope
from audit_shared.validation.evidence_validator import EvidenceValidator
from audit_shared.genai.client import GenAIClient
from audit_shared.genai.engine import GenAIEngine
from audit_shared.reporting.engine import ReportingEngine
from audit_shared.reporting.formatters import MarkdownFormatter, TerminalFormatter

def hydrate_dataset(data: dict) -> CrawlDataset:
    pages = []
    for p in data.get('pages', []):
        ext = p.get('extracted', {})
        extracted = ExtractedData(**{k:v for k,v in ext.items() if k != 'date_candidates'})
        extracted.date_candidates = [DateCandidate(**dc) for dc in ext.get('date_candidates', [])]
        
        diag = p.get('diagnostics', {})
        diagnostics = ExtractionDiagnostics(**diag)
        
        pages.append(PageRecord(
            url=p['url'],
            final_url=p.get('final_url', ''),
            status_code=p.get('status_code', 0),
            content_type=p.get('content_type', ''),
            depth=p.get('depth', 0),
            parent_url=p.get('parent_url'),
            redirect_chain=p.get('redirect_chain', []),
            crawl_status=p.get('crawl_status', 'success'),
            raw_html=p.get('raw_html', ''),
            extracted=extracted,
            diagnostics=diagnostics
        ))
        
    stats = CrawlStats(**data.get('crawl_stats', {}))
    diags = CrawlDiagnostics(**data.get('crawl_diagnostics', {}))
    
    return CrawlDataset(
        seed_url=data.get('seed_url', ''),
        crawled_at=data.get('crawled_at', ''),
        pages=pages,
        crawl_stats=stats,
        crawl_diagnostics=diags,
        raw_scrapy_stats=data.get('raw_scrapy_stats', {}),
        unfetched_urls=data.get('unfetched_urls', [])
    )

@pytest.fixture(scope="module")
def fixture_server():
    server = start_server(port=0)
    yield server
    server.shutdown()

def test_master_pipeline_e2e(fixture_server):
    port = fixture_server.server.server_port
    target_url = f"http://127.0.0.1:{port}/"
    config = CrawlSettings(target_url=target_url, crawl_depth=2, page_limit=50)
    
    # 1. Crawl
    raw_data = run_crawl(target_url, config)
    dataset = hydrate_dataset(raw_data)
    
    # 2. Deterministic Rules
    registry = RuleRegistry()
    register_ai_discoverability_rules(registry)
    register_freshness_rules(registry)
    register_engagement_rules(registry)
    result = RuleEngine.run(dataset, registry)
    
    # 3. NLP Rules
    nlp_client = NLPClient(use_mock=True)
    semantic_rule = SemanticTopicRule(client=nlp_client)
    nlp_results = asyncio.run(semantic_rule.evaluate(dataset))
    semantic_findings = SemanticInterpreter.interpret(nlp_results)
    result.findings.extend(semantic_findings)
    
    # Verify NLP distinct states on specific fixtures before they get grouped/validated away if invalid
    # The SemanticInterpreter maps NLP items to findings. Let's look at nlp_results instead.
    nlp_by_url = {res.page_url: res for res in nlp_results}
    
    nlp_alignment_url = f"http://127.0.0.1:{port}/nlp_alignment"
    nlp_mismatch_url = f"http://127.0.0.1:{port}/nlp_mismatch"
    unsupported_lang_url = f"http://127.0.0.1:{port}/unsupported_lang"
    insufficient_text_url = f"http://127.0.0.1:{port}/insufficient_text"
    
    # eligible -> analyzed -> no observation
    assert nlp_alignment_url in nlp_by_url
    assert nlp_by_url[nlp_alignment_url].state.name == "ANALYSIS_NO_OBSERVATION"
    
    # eligible -> analyzed -> semantic observation
    assert nlp_mismatch_url in nlp_by_url
    assert nlp_by_url[nlp_mismatch_url].state.name == "ANALYSIS_SUCCESS"
    assert nlp_by_url[nlp_mismatch_url].observation is not None
    
    # unsupported language -> skipped
    assert unsupported_lang_url in nlp_by_url
    assert nlp_by_url[unsupported_lang_url].state.name == "UNSUPPORTED_LANGUAGE"
    
    # insufficient text -> skipped
    assert insufficient_text_url in nlp_by_url
    assert nlp_by_url[insufficient_text_url].state.name == "SKIPPED_BY_GATE"

    # 4. Grouping
    scope = EvaluationScope(
        html_pages_crawled=dataset.crawl_stats.html_pages_crawled,
        successful_pages=dataset.crawl_stats.successful_pages,
        total_pages_evaluated=len(dataset.pages),
        is_truncated=len(dataset.unfetched_urls) > 0
    )
    grouped_results = GroupDeduplicator.process(result.findings, scope)
    
    # 5. Evidence Validation
    validation_result = EvidenceValidator.validate_all(grouped_results, dataset, scope)
    
    # Verify Grouping & Evidence preserved the findings
    valid_group_ids = [g.canonical_finding.trigger.rule_id for g in validation_result.valid_groups]
    
    # Regression cases for Nofollow
    assert "AI-ROBOTS-002" in valid_group_ids # /noindex_page
    assert "AI-ROBOTS-003" in valid_group_ids # /nofollow_only and /noindex_page
    # Note: /index_follow triggers neither
    
    # 6. GenAI
    genai_client = GenAIClient(use_mock=True)
    genai_engine = GenAIEngine(client=genai_client)
    genai_diagnostics = asyncio.run(genai_engine.enrich_groups(validation_result.valid_groups))
    
    # 7. Reporting
    final_report = ReportingEngine.generate_report(dataset, validation_result)
    final_report.genai_diagnostics = genai_diagnostics
    
    # Convert to outputs
    report_dict = final_report.to_dict()
    markdown_str = MarkdownFormatter.generate(final_report)
    terminal_str = TerminalFormatter.generate(final_report)
    
    # 8. Verifications on Output Consistency
    # JSON has correct structure
    assert "findings" in report_dict
    assert "diagnostics" in report_dict
    assert "overall_score" in report_dict["summary"]
    
    report_findings = report_dict["findings"]
    assert len(report_findings) == len(validation_result.valid_groups)
    assert report_dict["summary"]["total_findings"] == len(validation_result.valid_groups)
    
    # Final JSON findings match what is written in Markdown / Terminal
    # We can check simple string presence in markdown/terminal for rule IDs
    for g in validation_result.valid_groups:
        assert g.canonical_finding.title in markdown_str
        
    # Check severity count consistency
    reported_severity_counts = report_dict["summary"]["severity"]
    actual_critical = sum(1 for f in report_findings if f["severity"] == "critical")
    actual_high = sum(1 for f in report_findings if f["severity"] == "high")
    actual_medium = sum(1 for f in report_findings if f["severity"] == "medium")
    actual_low = sum(1 for f in report_findings if f["severity"] == "low")
    
    # "critical" is not in SeveritySummary, check it manually or skip
    assert reported_severity_counts.get("critical", 0) == actual_critical
    assert reported_severity_counts["high"] == actual_high
    assert reported_severity_counts["medium"] == actual_medium
    assert reported_severity_counts["low"] == actual_low
    
    # 9. Verify Finding Contract Survives
    # Let's inspect AI-ROBOTS-002 as a representative finding
    noindex_finding = next((f for f in report_findings if f["trigger"]["rule_id"] == "AI-ROBOTS-002"), None)
    assert noindex_finding is not None
    assert "pipeline" in noindex_finding
    assert "title" in noindex_finding
    assert "severity" in noindex_finding
    assert "trigger" in noindex_finding
    assert "evidence" in noindex_finding
    assert "affected_pages" in noindex_finding["evidence"]
    assert "suggested_action" in noindex_finding
    
    # 10. Verify Freshness distinct states
    # Freshness findings should explicitly exist for positive triggers
    assert "FR-CONS-001" in valid_group_ids # Contradictory dates or stale article
    
    # 11. Partial Crawl Honesty
    # Verify that we do not have a finding claiming 404 for an unfetched URL
    # /broken_link_source links to /404 which should be fetched
    assert "AI-LINK-001" in valid_group_ids # Broken internal link should be present
    # In this dataset, there shouldn't be any "Unfetched because bounds" mapped to 404
    # The Evidence Validator drops findings where evidence pages aren't actually 404s in the dataset if they are reported as such
    broken_link_finding = next((f for f in report_findings if f["id"] == "AI-LINK-001"), None)
    if broken_link_finding:
        assert broken_link_finding["evidence"]["observed_value"] == "404"
