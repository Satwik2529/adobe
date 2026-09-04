import json
import pytest
from audit_shared.models.data_flow import CrawlDataset

def test_crawldataset_serialization():
    # Make sure we can create an empty dataset and serialize it
    # runner.py uses dataclasses.asdict to return dict, but let's test dataclass directly
    ds = CrawlDataset(seed_url="http://example.com", crawled_at="2023-01-01T00:00:00Z")
    from dataclasses import asdict
    d = asdict(ds)
    assert d['seed_url'] == "http://example.com"
    assert 'crawl_stats' in d
    assert d['crawl_stats']['html_pages_crawled'] == 0
    # ensure it's json serializable
    js = json.dumps(d)
    assert "example.com" in js
