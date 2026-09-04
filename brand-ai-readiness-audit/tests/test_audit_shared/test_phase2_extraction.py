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
    server = start_server(port=5005)
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

def test_phase2_extraction(fixture_app):
    dataset = run_crawler_subprocess("http://127.0.0.1:5005/", depth=2, limit=50)
    pages = dataset['pages']
    
    # Verify Home Page Extraction
    home = next(p for p in pages if p['url'] == "http://127.0.0.1:5005/")
    assert home['extracted']['title'] == "Home"
    assert "Home OG" in home['extracted']['og_tags'][0]
    assert home['extracted']['page_type'] == "homepage"
    assert len(home['extracted']['detailed_internal_links']) > 0
    assert any("About" in l['text'] for l in home['extracted']['detailed_internal_links'])
    
    # Verify Article Extraction (dates, json_ld)
    article = next(p for p in pages if p['url'] == "http://127.0.0.1:5005/article")
    assert article['extracted']['page_type'] == "article"
    
    dates = article['extracted']['date_candidates']
    assert len(dates) >= 3, "Should extract meta and json_ld dates"
    
    parsed_json = article['extracted']['parsed_json_ld']
    assert len(parsed_json) >= 2, "Should parse @graph and array JSON-LD correctly"
    
    # Verify Malformed JSON-LD
    malformed = next(p for p in pages if p['url'] == "http://127.0.0.1:5005/malformed")
    assert malformed['diagnostics']['malformed_jsonld_count'] == 1
    
    # Verify Products
    product_a = next(p for p in pages if "products/a" in p['final_url'])
    assert product_a['extracted']['page_type'] == "product"
