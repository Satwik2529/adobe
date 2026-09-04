import sys
import os
import time

sys.path.insert(0, os.path.abspath('src'))
from audit_shared.crawl.runner import run_crawl

from audit_shared.config.settings import CrawlSettings

url = "https://example.com"
start_time = time.time()
config = CrawlSettings(target_url=url, page_limit=10, crawl_depth=1)
data = run_crawl(url, config)
duration = time.time() - start_time

results = data.get('results', [])
stats = data.get('stats', {})

print(f"URL: {url}")
print(f"pages_discovered: {stats.get('scheduler/enqueued', len(results))}")
print(f"pages_scheduled: {stats.get('scheduler/enqueued', len(results))}")
print(f"pages_crawled: {stats.get('response_received_count', len(results))}")
successful = len([r for r in results if r.get('status_code', 200) < 400])
failed = len([r for r in results if r.get('status_code', 200) >= 400])
print(f"pages_successful: {successful}")
print(f"pages_failed: {failed}")
print(f"redirects: {stats.get('downloader/response_status_count/301', 0) + stats.get('downloader/response_status_count/302', 0)}")
print(f"duration: {duration:.2f}s")
