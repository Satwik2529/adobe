import pytest
from audit_shared.reporting.models import FinalReport, SeveritySummary, CrawlMetrics, EvaluationScope, DiagnosticSummary
from audit_shared.models.finding import Finding, Pipeline, Severity, Trigger, TriggerType, generate_finding_id

def test_final_report_json_keys():
    summary = SeveritySummary(score=100, total_findings=0, high=0, medium=0, low=0, info=0)
    crawl = CrawlMetrics(
        urls_discovered=10, urls_scheduled=10, requests_attempted=10, responses_received=10,
        html_pages_crawled=10, successful_pages=10, failed_pages=0, robots_blocked=0,
        duplicate_urls=0, redirects=0, non_html_responses=0, crawl_duration_seconds=5.0
    )
    scope = EvaluationScope(
        status="success", reason="ok", pages_evaluated=10, max_pages=100,
        max_depth=2, robots_respected=True, termination_reason="finished"
    )
    diagnostics = DiagnosticSummary(findings_evaluated=0, evidence_valid_findings=0, excluded_findings=0)
    
    report = FinalReport(
        site="https://example.com",
        audited_at="2024-01-01T12:00:00Z",
        summary=summary,
        crawl=crawl,
        evaluation_scope=scope,
        findings=[],
        diagnostics=diagnostics
    )
    
    data = report.to_dict()
    
    assert "site" in data
    assert "audited_at" in data
    assert "summary" in data
    assert "crawl" in data
    assert "evaluation_scope" in data
    assert "findings" in data
    assert "diagnostics" in data
    
    assert data["site"] == "https://example.com"
    assert data["audited_at"] == "2024-01-01T12:00:00Z"
    
    # Asserting exact keys
    assert set(data.keys()) == {"site", "audited_at", "summary", "crawl", "evaluation_scope", "findings", "diagnostics"}

def test_markdown_and_terminal_generation():
    from audit_shared.reporting.formatters import MarkdownFormatter, TerminalFormatter
    
    summary = SeveritySummary(score=100, total_findings=0, high=0, medium=0, low=0, info=0)
    crawl = CrawlMetrics(
        urls_discovered=10, urls_scheduled=10, requests_attempted=10, responses_received=10,
        html_pages_crawled=10, successful_pages=10, failed_pages=0, robots_blocked=0,
        duplicate_urls=0, redirects=0, non_html_responses=0, crawl_duration_seconds=5.0
    )
    scope = EvaluationScope(
        status="success", reason="ok", pages_evaluated=10, max_pages=100,
        max_depth=2, robots_respected=True, termination_reason="finished"
    )
    diagnostics = DiagnosticSummary(findings_evaluated=0, evidence_valid_findings=0, excluded_findings=0)
    
    # Test without genai
    report_no_genai = FinalReport(
        site="https://example.com",
        audited_at="2024-01-01T12:00:00Z",
        summary=summary,
        crawl=crawl,
        evaluation_scope=scope,
        findings=[],
        diagnostics=diagnostics
    )
    
    md_out = MarkdownFormatter.generate(report_no_genai)
    term_out = TerminalFormatter.generate(report_no_genai)
    
    assert "AI Readiness Audit Report" in md_out
    assert "https://example.com" in md_out
    assert "Audit Complete" in term_out
    assert "GenAI Diagnostics" not in term_out
    
    # Test with finding and genai
    # Test with finding and genai
    from audit_shared.models.finding import GenAIContext, Evidence, SuggestedAction, ActionPriority
    finding = Finding(
        id="T1", pipeline=Pipeline.AI_DISCOVERABILITY, title="Test Issue",
        severity=Severity.HIGH, trigger=Trigger(rule_id="R1", type=TriggerType.DETERMINISTIC),
        evidence=Evidence(observed_value="test"),
        suggested_action=SuggestedAction(summary="Fix it", priority=ActionPriority.HIGH)
    )
    finding.genai = GenAIContext(
        used=True, explanation="Expl", why_it_matters="Why", possible_solution="Sol"
    )
    report_no_genai.findings = [finding]
    
    md_out_genai = MarkdownFormatter.generate(report_no_genai)
    assert "GenAI Context" in md_out_genai
    assert "Expl" in md_out_genai
    
    # Add diagnostic GenAI to test terminal output
    from audit_shared.genai.diagnostics import GenAIDiagnostics
    report_no_genai.diagnostics.genai = GenAIDiagnostics(
        eligible_groups=1, requests_attempted=1, successful=1, rate_limited=0,
        timeouts=0, provider_failures=0, invalid_responses=0, skipped_by_budget=0,
        total_duration_seconds=1.0
    )
    
    term_out_genai = TerminalFormatter.generate(report_no_genai)
    assert "GenAI Diagnostics" in term_out_genai
    assert "Eligible groups:          1" in term_out_genai
