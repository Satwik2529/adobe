import asyncio
from audit_shared.config.settings import CrawlSettings
from audit_shared.crawl.runner import run_crawl
from audit_shared.cli import hydrate_dataset
from audit_shared.rules.registry import RuleRegistry
from audit_shared.rules.ai_discoverability import register_ai_discoverability_rules
from audit_shared.rules.freshness import register_freshness_rules
from audit_shared.rules.engagement import register_engagement_rules
from audit_shared.rules.engine import RuleEngine
from audit_shared.nlp.client import NLPClient
from audit_shared.nlp.rules import SemanticTopicRule

def analyze():
    print("Running crawl to get dataset...")
    raw = run_crawl("https://arngren.net/", CrawlSettings(crawl_depth=3, page_limit=100))
    dataset = hydrate_dataset(raw)
    
    print("\n=== 3. CRAWLDATASET INSPECTION ===")
    missing = {
        'title': 0, 'meta_description': 0, 'h1s': 0, 'headings': 0, 
        'visible_text': 0, 'internal_links': 0, 'images': 0, 'canonical': 0, 
        'robots': 0, 'json_ld': 0, 'date_signals': 0, 'language': 0
    }
    for p in dataset.pages:
        e = p.extracted
        if not e.title: missing['title'] += 1
        if not e.meta_description: missing['meta_description'] += 1
        if not e.h1s: missing['h1s'] += 1
        if not e.headings: missing['headings'] += 1
        if not e.visible_text: missing['visible_text'] += 1
        if not e.internal_links: missing['internal_links'] += 1
        if not e.images: missing['images'] += 1
        if not e.canonical: missing['canonical'] += 1
        if not e.meta_robots: missing['robots'] += 1
        if not e.json_ld_blocks: missing['json_ld'] += 1
        if not e.date_candidates: missing['date_signals'] += 1
        if not e.language: missing['language'] += 1
        
    for k, v in missing.items():
        print(f"Pages missing {k}: {v} / {len(dataset.pages)}")
        
    print("\n=== 5. FRESHNESS ===")
    registry = RuleRegistry()
    register_freshness_rules(registry)
    result = RuleEngine.run(dataset, registry)
    print(f"Total freshness findings triggered by engine: {len(result.findings)}")
    print(f"Any dates available across dataset: {sum(1 for p in dataset.pages if p.extracted.date_candidates)}")
    
    print("\n=== 7. NLP / SEMANTIC ANALYSIS ===")
    nlp_client = NLPClient(use_mock=True)
    rule = SemanticTopicRule(client=nlp_client)
    
    from audit_shared.nlp.gating import CandidateGating
    
    candidates = CandidateGating.select_candidates(dataset)
    print(f"NLP Candidates initially selected: {len(candidates)}")
    
    eligible = []
    rejected = []
    for c in candidates:
        if CandidateGating.is_eligible(c):
            eligible.append(c)
        else:
            rejected.append(c)
            
    print(f"Eligible Candidates: {len(eligible)}")
    print(f"Rejected Candidates: {len(rejected)}")
    if rejected:
        print(f"Sample rejection reason (needs deeper trace, typically language or length):")
        # Let's see if we can manually trace one
        c = rejected[0]
        print(f"URL: {c.url}, text len: {len(c.extracted.visible_text) if c.extracted.visible_text else 0}, lang: {c.extracted.language}")
    
    if eligible:
        c = eligible[0]
        print(f"Sample Eligible URL: {c.url}")
        
if __name__ == "__main__":
    analyze()
