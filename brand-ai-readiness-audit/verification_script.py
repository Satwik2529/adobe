import json
import sys
import os
import time

sys.path.insert(0, os.path.abspath('src'))
from audit_shared.config.settings import CrawlSettings
from audit_shared.crawl.runner import run_crawl

sys.path.insert(0, os.path.abspath('tests/crawler'))
from fixture_server import start_server

def main():
    server = start_server(port=5001)
    time.sleep(1) # wait for server to start

    try:
        url = "http://127.0.0.1:5001/"
        config = CrawlSettings(target_url=url, page_limit=100, crawl_depth=10, respect_robots_txt=True)
        start_time = time.time()
        data = run_crawl(url, config)
        duration = time.time() - start_time
        
        results = data.get('results', [])
        stats = data.get('stats', {})
        
        print("--- SUMMARY ---")
        print(f"pages_discovered: {stats.get('scheduler/enqueued', 0)}")
        print(f"pages_scheduled: {stats.get('scheduler/enqueued', 0)}")
        print(f"pages_crawled: {stats.get('response_received_count', 0)}")
        successful = len([r for r in results if r.get('status_code', 0) < 400])
        failed = len([r for r in results if r.get('status_code', 0) >= 400])
        print(f"pages_successful: {successful}")
        print(f"pages_failed: {failed}")
        print(f"robots_blocked: {stats.get('robotstxt/forbidden', 0)}")
        print(f"duplicate_urls: {stats.get('dupefilter/filtered', 0)}")
        print(f"redirects: {stats.get('downloader/response_status_count/301', 0) + stats.get('downloader/response_status_count/302', 0)}")
        print(f"max_depth: {stats.get('request_depth_max', 0)}")
        print(f"crawl_duration: {duration:.2f}s")
        print("\n--- SAMPLE PAGE ---")
        for r in results:
            if r['url'] == url:
                print(json.dumps(r, indent=2))
                break
    finally:
        server.shutdown()

if __name__ == '__main__':
    main()
