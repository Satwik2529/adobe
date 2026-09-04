import pytest
from audit_shared.config.settings import CrawlSettings
from audit_shared.crawl.runner import run_crawl
from audit_shared.models.data_flow import CrawlDataset
from audit_shared.rules.registry import RuleRegistry
from audit_shared.rules.engine import RuleEngine
from audit_shared.rules.ai_discoverability import register_ai_discoverability_rules
from tests.test_audit_shared.test_phase4_e2e import hydrate_dataset

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'crawler')))
from fixture_server import start_server

@pytest.fixture(scope="module")
def fixture_app():
    server = start_server(port=5006)
    yield server
    server.shutdown()

def test_phase1_to_phase5_end_to_end(fixture_app):
    # Phase 1 & 2: Crawl and Extraction
    target_url = "http://127.0.0.1:5006/"
    config = CrawlSettings(target_url=target_url, crawl_depth=2, page_limit=50)
    
    raw_data = run_crawl(target_url, config)
    dataset = hydrate_dataset(raw_data)
    
    assert dataset.crawl_stats.html_pages_crawled > 0
    
    # Phase 4 & 5: Rule Engine + AI Discoverability Rules
    registry = RuleRegistry()
    register_ai_discoverability_rules(registry)
    
    results = RuleEngine.run(dataset, registry)
    
    # Phase 3: Provenance Validation is built into RuleEngine.
    # The E2E tests we just added to the fixture should have generated specific findings.
    
    all_findings = results.findings
        
    rule_ids_triggered = set(f.trigger.rule_id for f in all_findings)
    print("UNFETCHED:", raw_data.get('unfetched_urls'))
    print("TRIGGERED:", rule_ids_triggered)
    
    # Assert specific rules triggered correctly based on the fixture we created
    assert "AI-CRAWL-001" in rule_ids_triggered # /404 should trigger this
    assert "AI-CRAWL-002" in rule_ids_triggered # /500 should trigger this
    assert "AI-ROBOTS-001" in rule_ids_triggered # /private is blocked by robots.txt
    assert "AI-ROBOTS-002" in rule_ids_triggered # /noindex_page has noindex
    assert "AI-REDIRECT-001" in rule_ids_triggered # /redirect_chain_1 is a chain
    assert "AI-META-001" in rule_ids_triggered # /missing_title
    assert "AI-META-003" in rule_ids_triggered # /missing_title has no meta description
    assert "AI-HTML-001" in rule_ids_triggered # /missing_h1
    assert "AI-CANONICAL-002" in rule_ids_triggered # /canonical_broken
    assert "AI-LINK-001" in rule_ids_triggered # /broken_link_source -> /404
    assert "AI-CONTENT-001" in rule_ids_triggered # /exact_dup_1 and 2
    assert "AI-CONTENT-002" in rule_ids_triggered # /thin_content
    assert "AI-SCHEMA-001" in rule_ids_triggered # /malformed
    
    # Check invalid_findings counts across results to ensure no provenance violation
    for d in results.diagnostics:
        assert d.invalid_findings == 0, f"Provenance violations found for {d.rule_id}"
