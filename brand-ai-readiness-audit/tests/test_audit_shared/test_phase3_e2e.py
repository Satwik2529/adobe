import pytest
import json
import threading
import time
import os
import subprocess
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'crawler'))
from fixture_server import start_server

from audit_shared.models.finding import (
    Finding, Severity, Pipeline, TriggerType, ActionPriority, Trigger, SuggestedAction,
    Evidence, generate_finding_id
)
from audit_shared.models.data_flow import CrawlDataset, PageRecord, ExtractedData, CrawlStats, CrawlDiagnostics
from audit_shared.validation.finding_validator import FindingValidator

@pytest.fixture(scope="module")
def local_server():
    server = start_server(port=5006)
    yield "http://127.0.0.1:5006"
    server.shutdown()

def run_crawler_subprocess(url, depth=10, limit=100):
    script_path = os.path.join(os.path.dirname(__file__), '..', 'crawler', 'run_crawler_subprocess.py')
    result = subprocess.run(
        [sys.executable, script_path, url, str(depth), str(limit)],
        capture_output=True, text=True, check=True,
        cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    )
    for line in result.stdout.splitlines():
        if line.startswith('{'):
            return json.loads(line)
    return {}

def hydrate_dataset(data: dict) -> CrawlDataset:
    pages = []
    for p in data.get('pages', []):
        ext = p.get('extracted', {})
        extracted = ExtractedData(**{k:v for k,v in ext.items() if k != 'date_candidates'})
        pages.append(PageRecord(
            url=p['url'],
            final_url=p['final_url'],
            status_code=p['status_code'],
            content_type=p['content_type'],
            depth=p['depth'],
            parent_url=p['parent_url'],
            raw_html=p.get('raw_html', ''),
            extracted=extracted
        ))
    
    return CrawlDataset(
        seed_url=data.get('seed_url', ''),
        crawled_at=data.get('crawled_at', ''),
        pages=pages,
        crawl_stats=CrawlStats(**data.get('crawl_stats', {})),
        crawl_diagnostics=CrawlDiagnostics(**data.get('crawl_diagnostics', {})),
        raw_scrapy_stats=data.get('raw_scrapy_stats', {})
    )

def test_phase1_phase2_phase3_end_to_end(local_server):
    """
    Cumulative integration test proving Phase 1, Phase 2, and Phase 3 boundaries.
    """
    # 1. Phase 1 & 2: Run the actual crawler in a subprocess to generate a canonical dataset
    raw_dict = run_crawler_subprocess(local_server + "/", depth=2, limit=50)
    dataset = hydrate_dataset(raw_dict)

    # 2. E2E Verification of Previous Functionality (Phase 1 & 2)
    stats = dataset.crawl_stats
    
    # - internal pages are discovered
    assert stats.urls_discovered > 0
    # - recursive crawling occurs
    assert stats.html_pages_crawled > 1
    # - robots.txt is respected
    assert dataset.crawl_diagnostics.robots_txt_status == 200
    assert dataset.crawl_diagnostics.robots_txt_fetched is True
    # - robots-blocked URL is not fetched
    assert stats.robots_blocked >= 1
    # - redirects are tracked
    assert stats.redirects >= 1
    # - failed page is tracked
    assert stats.failed_pages >= 1
    # - non-HTML response is handled
    assert stats.non_html_responses >= 1
    # - html_pages_crawled is distinct from raw response count
    assert stats.html_pages_crawled != dataset.raw_scrapy_stats.get('response_received_count', 0)
    
    print("\nPhase 1 -> Phase 2 -> Phase 3 E2E Stats:")
    print(f"urls_discovered: {stats.urls_discovered}")
    print(f"urls_scheduled: {stats.urls_scheduled}")
    print(f"requests_attempted: {stats.requests_attempted}")
    print(f"responses_received: {stats.responses_received}")
    print(f"html_pages_crawled: {stats.html_pages_crawled}")
    print(f"successful_pages: {stats.successful_pages}")
    print(f"failed_pages: {stats.failed_pages}")
    print(f"robots_blocked: {stats.robots_blocked}")
    print(f"duplicate_urls: {stats.duplicate_urls}")
    print(f"redirects: {stats.redirects}")
    print(f"non_html_responses: {stats.non_html_responses}\n")

    # - CrawlDataset contains real PageRecords
    html_pages = [p for p in dataset.pages if 'text/html' in p.content_type]
    assert len(html_pages) == stats.html_pages_crawled
    
    # - extracted title/headings/links/schema data remain available
    about_page = next((p for p in dataset.pages if p.url.endswith('/about')), None)
    assert about_page is not None
    assert about_page.extracted.title == "About"
    assert "About" in about_page.extracted.headings
    # - raw HTML remains available
    assert "<title>About</title>" in about_page.raw_html

    # 3. Phase 3: Construct a Finding referencing an ACTUAL fetched PageRecord URL
    page_url = about_page.url
    
    finding = Finding(
        id=generate_finding_id("TEST-RULE", [page_url]),
        pipeline=Pipeline.AI_DISCOVERABILITY,
        title="Test E2E Finding",
        severity=Severity.HIGH,
        trigger=Trigger(rule_id="TEST-RULE", type=TriggerType.DETERMINISTIC),
        suggested_action=SuggestedAction(summary="Fix the test issue", priority=ActionPriority.HIGH),
        evidence=Evidence(
            page=page_url,
            source="extracted",
            field="title",
            observed_value=about_page.extracted.title,
            pages_checked=1,
            pages_affected=1,
            affected_percentage=100.0
        )
    )

    # 4. Phase 3: Validate Finding Provenance
    errors = FindingValidator.validate(finding, dataset)
    assert not errors, f"Provenance validation failed: {errors}"

    # 5. Phase 3: Serialization
    # Test json.dumps of Finding.to_dict() passes
    finding_dict = finding.to_dict()
    json_str = json.dumps(finding_dict)
    
    # And check the JSON representation
    reloaded = json.loads(json_str)
    assert reloaded["pipeline"] == "ai_discoverability"
    assert reloaded["evidence"]["page"] == page_url
