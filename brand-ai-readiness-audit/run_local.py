import sys
import os
import time
import json
import subprocess
import threading
from urllib.parse import urlparse

def run_flask():
    os.system("python tests/crawler/fixture_server.py")

flask_thread = threading.Thread(target=run_flask, daemon=True)
flask_thread.start()
time.sleep(3)

url = "http://127.0.0.1:5001/"
start_time = time.time()
cmd = [
    sys.executable,
    "tests/crawler/run_crawler_subprocess.py",
    url,
    "2",
    "100"
]
result = subprocess.run(cmd, capture_output=True, text=True)
duration = time.time() - start_time

data = json.loads(result.stdout.strip())
results = data.get('results', [])
stats = data.get('stats', {})

print("FLASK FIXTURE SMOKE TEST:")
print(f"pages_discovered: {stats.get('scheduler/enqueued', 'N/A')}")
print(f"pages_scheduled: {stats.get('scheduler/enqueued', 'N/A')}")
print(f"pages_crawled: {len(results)}")
print(f"pages_successful: {len([r for r in results if r.get('status_code', 200) < 400])}")
print(f"pages_failed: {len([r for r in results if r.get('status_code', 200) >= 400])}")
print(f"robots_blocked: {stats.get('robotstxt/forbidden', 0)}")
print(f"duplicate_urls: {stats.get('dupefilter/filtered', 0)}")
print(f"redirects: {stats.get('downloader/response_status_count/301', 0)}")
print(f"max_depth: 2")
print(f"crawl_duration: {duration:.2f}s")
# Just show 1 result to verify schema extraction
print("\nRepresentative result:")
if results:
    print(json.dumps(results[0], indent=2))
