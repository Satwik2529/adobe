import argparse
import sys
import json
import os

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
import asyncio
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
    
    print(f"Crawling {args.url} (depth={args.depth}, limit={args.limit})...")
    
    # We must run scrapy in a subprocess to avoid twisted reactor issues if this script is reused, 
    # but here we can just use run_crawl directly since it's a single run.
    raw_data = run_crawl(args.url, config)
    
    dataset = hydrate_dataset(raw_data)
    
    print(f"Crawled {len(dataset.pages)} pages successfully.")
    
    registry = RuleRegistry()
    register_ai_discoverability_rules(registry)
    register_freshness_rules(registry)
    register_engagement_rules(registry)
    
    result = RuleEngine.run(dataset, registry)
    
    print("Running Phase 10: Semantic/NLP Analysis...")
    nlp_client = NLPClient(use_mock=True) # use mock for now
    semantic_rule = SemanticTopicRule(client=nlp_client)
    nlp_results = asyncio.run(semantic_rule.evaluate(dataset))
    semantic_findings = SemanticInterpreter.interpret(nlp_results)
    
    print(f"Phase 10 produced {len(semantic_findings)} semantic findings.")
    result.findings.extend(semantic_findings)
    
    print(f"\n--- CRAWL STATS ---")
    print(f"urls_discovered: {dataset.crawl_stats.urls_discovered}")
    print(f"urls_scheduled: {dataset.crawl_stats.urls_scheduled}")
    print(f"requests_attempted: {dataset.crawl_stats.requests_attempted}")
    print(f"responses_received: {dataset.crawl_stats.responses_received}")
    print(f"html_pages_crawled: {dataset.crawl_stats.html_pages_crawled}")
    print(f"successful_pages: {dataset.crawl_stats.successful_pages}")
    print(f"failed_pages: {dataset.crawl_stats.failed_pages}")
    print(f"robots_blocked: {dataset.crawl_stats.robots_blocked}")
    print(f"redirects: {dataset.crawl_stats.redirects}")
    
    print(f"\nAudit completed. Evaluated {result.successful_rules} rules successfully, {result.failed_rules} failed.")
            
    print(f"Found {len(result.findings)} raw page-level findings.")
    
    # Run Phase 8 Grouping
    scope = EvaluationScope(
        html_pages_crawled=dataset.crawl_stats.html_pages_crawled,
        successful_pages=dataset.crawl_stats.successful_pages,
        total_pages_evaluated=len(dataset.pages),
        is_truncated=len(dataset.unfetched_urls) > 0
    )
    grouped_results = GroupDeduplicator.process(result.findings, scope)
    
    # Run Phase 9 Evidence Validation
    validation_result = EvidenceValidator.validate_all(grouped_results, dataset, scope)
    
    print(f"Grouped into {len(grouped_results)} aggregate findings.")
    print(f"Evidence Validation: {len(validation_result.valid_groups)} valid, {len(validation_result.invalid_groups)} invalid.")
    
    if validation_result.diagnostics:
        print("\n--- VALIDATION DIAGNOSTICS ---")
        for d in validation_result.diagnostics:
            print(f"[{d.finding_id}] FAILED:")
            for err in d.errors:
                print(f"  - {err}")
    
    canonical_findings = [g.canonical_finding for g in validation_result.valid_groups]
    
    if canonical_findings:
        print("\nFindings:")
        for f in canonical_findings:
            affected = f.evidence.pages_affected if f.evidence and f.evidence.pages_affected else 1
            print(f"  [{f.severity.name}] {f.trigger.rule_id} : {f.title} ({affected} pages affected) - {f.suggested_action.summary}")
            
    with open("dataset_dump.json", "w") as f:
        json.dump(raw_data, f, indent=2)
        
    findings_list = [f.to_dict() for f in canonical_findings]
    with open("findings_dump.json", "w") as f:
        json.dump(findings_list, f, indent=2)

if __name__ == "__main__":
    main()
