import os
import sys
import pytest
from audit_shared.config.settings import CrawlSettings
from audit_shared.crawl.runner import run_crawl

# Add tests/crawler to path to import fixture_server
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'crawler')))
from fixture_server import start_server

@pytest.fixture(scope="module")
def fixture_app():
    server = start_server(port=5004)
    yield server
    server.shutdown()

import subprocess
import json

def run_crawler_subprocess(url, depth=10, limit=100):
    script_path = os.path.join(os.path.dirname(__file__), '..', 'crawler', 'run_crawler_subprocess.py')
    result = subprocess.run(
        [sys.executable, script_path, url, str(depth), str(limit)],
        capture_output=True,
        text=True,
        cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    )
    return json.loads(result.stdout)

def test_phase2_metrics_invariants(fixture_app):
    dataset = run_crawler_subprocess("http://127.0.0.1:5004/", depth=2, limit=50)
    stats = dataset['crawl_stats']
    
    # Explicit deterministic fixture metric assertions
    assert stats['urls_discovered'] == 41, f"Expected 41, got {stats['urls_discovered']}"
    assert stats['urls_scheduled'] == 46, f"Expected 46, got {stats['urls_scheduled']}"
    assert stats['requests_attempted'] == 46, f"Expected 46, got {stats['requests_attempted']}"
    assert stats['responses_received'] == 41, f"Expected 41, got {stats['responses_received']}"
    assert stats['html_pages_crawled'] == 39, f"Expected 39, got {stats['html_pages_crawled']}"
    assert stats['successful_pages'] == 37, f"Expected 37, got {stats['successful_pages']}"
    assert stats['failed_pages'] == 2, f"Expected 2, got {stats['failed_pages']}"
    assert stats['robots_blocked'] == 1, f"Expected 1, got {stats['robots_blocked']}"
    assert stats['duplicate_urls'] == 3, f"Expected 3, got {stats['duplicate_urls']}"
    assert stats['redirects'] == 3, f"Expected 3, got {stats['redirects']}"
    assert stats['non_html_responses'] == 1, f"Expected 1, got {stats['non_html_responses']}"
    
    # 1. robots.txt is not an HTML page
    # Checked implicitly by non_html_responses and response count maths.
    
    # 2. robots-blocked URL is counted in robots_blocked
    assert stats['robots_blocked'] == 1, "Should have blocked /private"
    
    # 3. redirects do not incorrectly inflate successful_pages
    assert stats['successful_pages'] == 37
    assert stats['redirects'] == 3
    
    # 4. 404/500 HTML page is counted in failed_pages
    assert stats['failed_pages'] == 2, "Should have 2 failed pages (/404, /500)"
    
    # 5. non-HTML responses are counted separately
    assert stats['non_html_responses'] == 1, "Should have exactly 1 non-HTML response (/image.png)"
    
    # 6. duplicate URLs do not inflate unique urls_discovered
    assert stats['urls_discovered'] == 41
    
    # 7. every successful/failed page corresponds to a PageRecord
    html_pages = [p for p in dataset['pages'] if 'text/html' in p['content_type']]
    assert len(html_pages) == stats['html_pages_crawled']
    
    success_records = [p for p in html_pages if p['status_code'] < 400]
    fail_records = [p for p in html_pages if p['status_code'] >= 400]
    
    assert len(success_records) == stats['successful_pages']
    assert len(fail_records) == stats['failed_pages']
    assert stats['successful_pages'] + stats['failed_pages'] == stats['html_pages_crawled']
    
    # 8. Normalized metrics differ correctly from raw Scrapy metrics
    raw = dataset['raw_scrapy_stats']
    assert stats['html_pages_crawled'] != raw.get('response_received_count', 0), "HTML pages shouldn't equal raw response count"
    
    # Verify robots.txt status is populated
    assert dataset['crawl_diagnostics']['robots_txt_status'] == 200, "Should have captured 200 status for robots.txt"
