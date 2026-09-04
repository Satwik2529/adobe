import pytest
from audit_shared.rules.registry import RuleRegistry
from audit_shared.rules.engine import RuleEngine
from tests.test_audit_shared.test_phase4_e2e import hydrate_dataset, run_crawler_subprocess
from audit_shared.rules.freshness import register_freshness_rules
from audit_shared.rules.ai_discoverability import register_ai_discoverability_rules
from audit_shared.models.finding import Finding
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'crawler')))
from fixture_server import start_server
import time

@pytest.fixture(scope="module")
def fixture_server():
    server = start_server(port=5008)
    yield "http://127.0.0.1:5008"
    server.shutdown()

def test_phase6_e2e_freshness(fixture_server):
    # 1. Real Scrapy crawl via subprocess to avoid Twisted Reactor collision
    raw_data = run_crawler_subprocess(fixture_server, depth=3, limit=50)
    dataset = hydrate_dataset(raw_data)
    
    print("CRAWLED URLs:", [p.url for p in dataset.pages])
    
    assert dataset is not None
    assert len(dataset.pages) >= 10, "Should have crawled multiple pages"
    
    # 2. Rule Engine with Phase 5 + 6
    registry = RuleRegistry()
    register_ai_discoverability_rules(registry)
    register_freshness_rules(registry)
    
    # 3. Evaluate
    result = RuleEngine.run(dataset, registry)
    
    # Check that we ran rules successfully
    assert result.successful_rules > 0
    assert result.failed_rules == 0
    
    findings = result.findings
    
    # Check specific freshness findings from the fixtures
    freshness_findings = [f for f in findings if f.pipeline.value == "freshness"]
    print("FRESHNESS FINDINGS:", [(f.trigger.rule_id, f.evidence.page) for f in freshness_findings])
    
    # We should have triggered several rules:
    # FR-DATE-001 on /missing_date_article (since it's an article missing a date)
    assert any(f.trigger.rule_id == "FR-DATE-001" and "missing_date_article" in f.evidence.page for f in freshness_findings)
    
    # FR-DATE-002 on /invalid_date
    assert any(f.trigger.rule_id == "FR-DATE-002" and "invalid_date" in f.evidence.page for f in freshness_findings)
    
    # FR-DATE-003 on /impossible_date
    assert any(f.trigger.rule_id == "FR-DATE-003" and "impossible_date" in f.evidence.page for f in freshness_findings)
    
    # FR-DATE-004 on /future_date
    assert any(f.trigger.rule_id == "FR-DATE-004" and "future_date" in f.evidence.page for f in freshness_findings)
    
    # FR-CONS-001 on /contradictory_dates
    assert any(f.trigger.rule_id == "FR-CONS-001" and "contradictory_dates" in f.evidence.page for f in freshness_findings)
    
    # FR-CONS-002 on /meta_jsonld_conflict
    assert any(f.trigger.rule_id == "FR-CONS-002" and "meta_jsonld_conflict" in f.evidence.page for f in freshness_findings)
    
    # FR-STALE-001 on /stale_article
    assert any(f.trigger.rule_id == "FR-STALE-001" and "stale_article" in f.evidence.page for f in freshness_findings)
    
    # FR-STALE-002 on /stale_product
    assert any(f.trigger.rule_id == "FR-STALE-002" and "stale_product" in f.evidence.page for f in freshness_findings)
    
    # Must NOT trigger
    # fresh_article -> no staleness
    assert not any(f.trigger.rule_id == "FR-STALE-001" and "fresh_article" in f.evidence.page for f in freshness_findings)
    
    # same_instant_diff_tz -> no contradiction
    assert not any(f.trigger.rule_id == "FR-CONS-002" and "same_instant_diff_tz" in f.evidence.page for f in freshness_findings)
    
    # date_only_vs_datetime -> no contradiction
    assert not any(f.trigger.rule_id == "FR-CONS-002" and "date_only_vs_datetime" in f.evidence.page for f in freshness_findings)
    
    # unknown_old_date -> no staleness
    assert not any(f.trigger.rule_id == "FR-STALE-001" and "unknown_old_date" in f.evidence.page for f in freshness_findings)
    
    # evergreen_old_date -> no staleness
    assert not any(f.trigger.rule_id == "FR-STALE-001" and "evergreen_old_date" in f.evidence.page for f in freshness_findings)
