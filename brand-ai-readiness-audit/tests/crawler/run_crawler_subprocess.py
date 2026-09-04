import sys
import os
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))

from audit_shared.crawl.runner import run_crawl
from audit_shared.config.settings import CrawlSettings


if __name__ == "__main__":
    url = sys.argv[1]
    depth = int(sys.argv[2])
    page_limit = int(sys.argv[3])
    
    config = CrawlSettings(
        target_url=url,
        crawl_depth=depth,
        page_limit=page_limit
    )
    
    data = run_crawl(url, config)
    print(json.dumps(data))
