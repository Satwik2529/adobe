import argparse
import sys
import json
import os
import time
import asyncio

from audit_shared.config.settings import CrawlSettings
from audit_shared.crawl.runner import run_crawl
from audit_shared.rules.registry import RuleRegistry
from audit_shared.rules.ai_discoverability import register_ai_discoverability_rules
from audit_shared.rules.freshness import register_freshness_rules
from audit_shared.rules.engagement import register_engagement_rules
from audit_shared.rules.engine import RuleEngine
from audit_shared.models.data_flow import CrawlDataset, PageRecord, ExtractedData, ExtractionDiagnostics, CrawlStats, CrawlDiagnostics, DateCandidate
from audit_shared.models.grouping import EvaluationScope
from audit_shared.grouping.deduplicator import GroupDeduplicator
from audit_shared.validation.evidence_validator import EvidenceValidator
from audit_shared.nlp.client import NLPClient
from audit_shared.nlp.rules import SemanticTopicRule
from audit_shared.nlp.interpreter import SemanticInterpreter

from audit_shared.genai.client import GenAIClient
from audit_shared.genai.engine import GenAIEngine
from audit_shared.genai.diagnostics import StageTiming

def hydrate_dataset(data: dict) -> CrawlDataset:
    pages = []
    for p in data.get('pages', []):
        ext = p.get('extracted', {})
        extracted = ExtractedData(**{k:v for k,v in ext.items() if k != 'date_candidates'})
        
        if 'date_candidates' in ext:
            extracted.date_candidates = [DateCandidate(**dc) for dc in ext['date_candidates']]
            
        diag_data = p.get('diagnostics', {})
        diagnostics = ExtractionDiagnostics(**diag_data)
        pages.append(PageRecord(
            url=p['url'],
            final_url=p['final_url'],
            status_code=p['status_code'],
            content_type=p['content_type'],
            depth=p['depth'],
            parent_url=p['parent_url'],
            redirect_chain=p.get('redirect_chain', []),
            crawl_status=p.get('crawl_status', 'success'),
            raw_html=p.get('raw_html', ''),
            extracted=extracted,
            diagnostics=diagnostics
        ))
    
    return CrawlDataset(
        seed_url=data.get('seed_url', ''),
        crawled_at=data.get('crawled_at', ''),
        pages=pages,
        crawl_stats=CrawlStats(**data.get('crawl_stats', {})),
        crawl_diagnostics=CrawlDiagnostics(**data.get('crawl_diagnostics', {})),
        raw_scrapy_stats=data.get('raw_scrapy_stats', {}),
        unfetched_urls=data.get('unfetched_urls', [])
    )

def main():
    parser = argparse.ArgumentParser(description="AI Readiness Audit CLI")
    parser.add_argument("url", help="Target URL to audit")
    parser.add_argument("--depth", type=int, default=2, help="Crawl depth limit")
    parser.add_argument("--limit", type=int, default=20, help="Page limit")
    
    args = parser.parse_args()
    
    config = CrawlSettings(
        target_url=args.url,
        crawl_depth=args.depth,
        page_limit=args.limit
    )
    
    stage_timing = StageTiming()
    t_start_total = time.time()
    
    print("[1/5] Crawling domain... ", end="", flush=True)
    t0 = time.time()
    raw_data = run_crawl(args.url, config)
    dataset = hydrate_dataset(raw_data)
    stage_timing.crawling = time.time() - t0
    print("OK")
    
    print("[2/5] Executing rule engines... ", end="", flush=True)
    t0 = time.time()
    registry = RuleRegistry()
    register_ai_discoverability_rules(registry)
    register_freshness_rules(registry)
    register_engagement_rules(registry)
    result = RuleEngine.run(dataset, registry)
    stage_timing.rule_engines = time.time() - t0
    
    t0 = time.time()
    nlp_client = NLPClient(use_mock=True) # use mock for now
    semantic_rule = SemanticTopicRule(client=nlp_client)
    nlp_results = asyncio.run(semantic_rule.evaluate(dataset))
    semantic_findings = SemanticInterpreter.interpret(nlp_results)
    result.findings.extend(semantic_findings)
    stage_timing.nlp = time.time() - t0
    print("OK")
    
    print("[3/5] Grouping & validating evidence... ", end="", flush=True)
    # Run Phase 8 Grouping
    scope = EvaluationScope(
        html_pages_crawled=dataset.crawl_stats.html_pages_crawled,
        successful_pages=dataset.crawl_stats.successful_pages,
        total_pages_evaluated=len(dataset.pages),
        is_truncated=len(dataset.unfetched_urls) > 0
    )
    t0 = time.time()
    grouped_results = GroupDeduplicator.process(result.findings, scope)
    stage_timing.grouping = time.time() - t0
    
    # Run Phase 9 Evidence Validation
    t0 = time.time()
    validation_result = EvidenceValidator.validate_all(grouped_results, dataset, scope)
    stage_timing.evidence_validation = time.time() - t0
    print("OK")
    
    print("[4/5] Generative AI explanations... ", end="", flush=True)
    t0 = time.time()
    genai_client = GenAIClient(use_mock=True)
    genai_engine = GenAIEngine(client=genai_client)
    genai_diagnostics = asyncio.run(genai_engine.enrich_groups(validation_result.valid_groups))
    stage_timing.genai = time.time() - t0
    print("OK")
    
    print("[5/5] Generating report... ", end="", flush=True)
    t0 = time.time()
    from audit_shared.reporting.engine import ReportingEngine
    from audit_shared.reporting.formatters import MarkdownFormatter, TerminalFormatter
    
    final_report = ReportingEngine.generate_report(dataset, validation_result)
    final_report.genai_diagnostics = genai_diagnostics
    
    stage_timing.total = time.time() - t_start_total
    
    # Needs to be captured before formatting, because formatter uses the object
    stage_timing.reporting = time.time() - t0 
    final_report.stage_timing = stage_timing
    
    # Re-calculate total to include reporting just in case, or just freeze it here
    final_report.stage_timing.total = time.time() - t_start_total
    
    # Generate artifacts
    with open("report.json", "w", encoding="utf-8") as f:
        json.dump(final_report.to_dict(), f, indent=2)
        
    with open("report.md", "w", encoding="utf-8") as f:
        f.write(MarkdownFormatter.generate(final_report))
        
    print("OK\n")
    
    # Print clean terminal output
    print(TerminalFormatter.generate(final_report))

if __name__ == "__main__":
    main()
