import sys
import os
import json
import time

sys.path.insert(0, os.path.abspath('src'))
sys.path.insert(0, os.path.abspath('tests/crawler'))

from audit_shared.config.settings import CrawlSettings
from audit_shared.crawl.runner import run_crawl
from fixture_server import start_server

if __name__ == '__main__':
    server = start_server(port=5006)
    try:
        config = CrawlSettings(
            target_url="http://127.0.0.1:5006/",
            page_limit=50,
            crawl_depth=2,
            respect_robots_txt=True
        )
        dataset = run_crawl("http://127.0.0.1:5006/", config)
        
        print("====== NORMALIZED METRICS ======")
        print(json.dumps(dataset['crawl_stats'], indent=2))
        
        print("\n====== RAW METRICS ======")
        print(json.dumps(dataset['raw_scrapy_stats'], indent=2))
        
        print("\n====== HTML PAGE METRIC PROOF ======")
        responses = dataset['raw_scrapy_stats'].get('response_received_count', 0)
        html_pages = dataset['crawl_stats']['html_pages_crawled']
        print(f"responses_received = {responses}")
        print(f"html_pages_crawled = {html_pages}")
        
        print("\n====== URL DISCOVERY SEMANTICS ======")
        print(f"urls_discovered = {dataset['crawl_stats']['urls_discovered']}")
        
        print("\n====== COMPLETE PageRecord PROOF ======")
        article_page = next((p for p in dataset['pages'] if p['url'] == "http://127.0.0.1:5006/article"), dataset['pages'][0])
        # truncate raw_html for display
        display_page = article_page.copy()
        raw_len = len(display_page['raw_html'])
        display_page['raw_html'] = display_page['raw_html'][:100] + f"... [TRUNCATED, FULL LENGTH: {raw_len} chars]"
        print(json.dumps(display_page, indent=2))
        
        print("\n====== COMPLETE EXTRACTION PROOF ======")
        print("Extracted from Article Page:")
        print(json.dumps(article_page['extracted'], indent=2))
        
        print("\n====== JSON SERIALIZATION PROOF ======")
        try:
            json_str = json.dumps(dataset)
            print("Serialization succeeded. Length:", len(json_str))
        except Exception as e:
            print("Serialization failed:", str(e))
            
        print("\n====== INCOMPLETE CRAWL PROOF ======")
        print(json.dumps(dataset['crawl_diagnostics'], indent=2))
        
    finally:
        server.shutdown()
