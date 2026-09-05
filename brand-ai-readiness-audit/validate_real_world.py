import asyncio
import json
import sys
import os

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from audit_shared.config.settings import load_config
from audit_shared.crawl.runner import run_crawl
from audit_shared.rules.registry import RuleRegistry
from audit_shared.rules.ai_discoverability import register_ai_discoverability_rules
from audit_shared.rules.freshness import register_freshness_rules
from audit_shared.rules.engagement import register_engagement_rules
from audit_shared.rules.engine import RuleEngine
from audit_shared.nlp.client import NLPClient
from audit_shared.nlp.rules import SemanticTopicRule
from audit_shared.nlp.interpreter import SemanticInterpreter
from audit_shared.grouping.deduplicator import GroupDeduplicator
from audit_shared.validation.evidence_validator import EvidenceValidator
from audit_shared.genai.client import GenAIClient
from audit_shared.genai.engine import GenAIEngine
from audit_shared.reporting.engine import ReportingEngine
from audit_shared.reporting.formatters import TerminalFormatter
from audit_shared.models.grouping import EvaluationScope
from audit_shared.models.data_flow import CrawlDataset, ExtractedData, PageRecord, DateCandidate, ExtractionDiagnostics, CrawlStats, CrawlDiagnostics

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

def run_full_pipeline(target_url: str):
    print(f"Starting Real-World Validation for: {target_url}")
    config = load_config()
    config.crawl.target_url = target_url
    config.crawl.page_limit = 5 # Limit for testing
    config.crawl.crawl_depth = 1
    
    # 1. Crawl (Runs its own reactor)
    raw_data = run_crawl(target_url, config.crawl)
    dataset = hydrate_dataset(raw_data)
    
    # 2. Async remaining steps
    asyncio.run(run_async_steps(dataset))

async def run_async_steps(dataset):
    # 2. Deterministic Rules
    registry = RuleRegistry()
    register_ai_discoverability_rules(registry)
    register_freshness_rules(registry)
    register_engagement_rules(registry)
    result = RuleEngine.run(dataset, registry)
    
    # 3. NLP Rules
    nlp_client = NLPClient(use_mock=True)
    semantic_rule = SemanticTopicRule(client=nlp_client)
    nlp_results = await semantic_rule.evaluate(dataset)
    semantic_findings = SemanticInterpreter.interpret(nlp_results)
    result.findings.extend(semantic_findings)
    
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
    
    # 6. GenAI
    genai_client = GenAIClient(use_mock=True)
    genai_engine = GenAIEngine(client=genai_client)
    genai_diagnostics = await genai_engine.enrich_groups(validation_result.valid_groups)
    
    # 7. Reporting
    report = ReportingEngine.generate_report(dataset, validation_result)
    report.diagnostics.genai = genai_diagnostics
    
    output = TerminalFormatter.generate(report)
    print(output)
    print("\n" + "="*50 + "\n")

def main():
    if len(sys.argv) > 1:
        target_url = sys.argv[1]
    else:
        target_url = "https://example.com"
        
    run_full_pipeline(target_url)

if __name__ == "__main__":
    main()
