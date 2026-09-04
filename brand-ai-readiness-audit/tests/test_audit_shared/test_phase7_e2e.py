import pytest
from audit_shared.crawl.runner import run_crawl
from audit_shared.config.settings import CrawlSettings
from audit_shared.cli import hydrate_dataset
from audit_shared.rules.registry import RuleRegistry
from audit_shared.rules.engine import RuleEngine
from audit_shared.rules.ai_discoverability import register_ai_discoverability_rules
from audit_shared.rules.freshness import register_freshness_rules
from audit_shared.rules.engagement import register_engagement_rules
from tests.test_audit_shared.test_phase4_e2e import run_crawler_subprocess
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'crawler')))
from fixture_server import start_server
import pytest

@pytest.fixture(scope="module")
def fixture_server():
    server = start_server(port=5009)
    yield "http://127.0.0.1:5009", server
    server.shutdown()

def test_phase7_e2e_cumulative_mock_server(fixture_server):
    """
    Cumulative E2E test verifying Phase 5, Phase 6, and Phase 7 rules run 
    together successfully using the mock HTTP server.
    """
    url, server = fixture_server
    
    # Hit the specific Phase 7 page which has an Article and 0 links, plus an empty alt image
    test_url = url + "/phase7_e2e"
    
    # Run the crawler in a subprocess to avoid twisted reactor issues
    raw_data = run_crawler_subprocess(test_url, depth=1, limit=5)
    
    # Hydrate
    dataset = hydrate_dataset(raw_data)
    assert len(dataset.pages) == 1
    
    # Register all rules
    registry = RuleRegistry()
    register_ai_discoverability_rules(registry)
    register_freshness_rules(registry)
    register_engagement_rules(registry)
    
    # Evaluate
    result = RuleEngine.run(dataset, registry)
    
    # Ensure no rule execution failures
    assert result.failed_rules == 0
    assert result.successful_rules > 0
    
    # Verify Phase 7 rules specifically triggered
    # The page is an "article" (via JSON-LD or extraction fallback, actually spider assigns article if Article schema exists)
    # It has 0 links, so ENG-NAV-001 should trigger.
    # It has 1 image with empty alt, so ENG-MEDIA-001 should trigger.
    
    findings_by_rule = {}
    for f in result.findings:
        findings_by_rule.setdefault(f.trigger.rule_id, []).append(f)
        
    assert "ENG-NAV-001" in findings_by_rule
    assert "ENG-MEDIA-001" in findings_by_rule
