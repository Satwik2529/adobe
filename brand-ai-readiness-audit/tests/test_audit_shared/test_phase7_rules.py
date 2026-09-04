import pytest
from audit_shared.models.data_flow import CrawlDataset, PageRecord, ExtractedData
from audit_shared.rules.engagement import DeadEndContentRule, MissingImageAltRule
from audit_shared.models.finding import Severity

def test_dead_end_content_rule():
    rule = DeadEndContentRule()
    
    # 1. Article with outbound internal links (Pass)
    p1 = PageRecord(
        url="http://example.com/a1",
        final_url="http://example.com/a1",
        status_code=200,
        content_type="text/html",
        depth=1,
        parent_url=None,
        extracted=ExtractedData(
            page_type="article",
            internal_links=["http://example.com/other"]
        )
    )
    
    # 2. Article with only self-links (Fail)
    p2 = PageRecord(
        url="http://example.com/a2",
        final_url="http://example.com/a2",
        status_code=200,
        content_type="text/html",
        depth=1,
        parent_url=None,
        extracted=ExtractedData(
            page_type="article",
            internal_links=["http://example.com/a2#section"]
        )
    )
    
    # 3. Unknown page type with no links (Pass)
    p3 = PageRecord(
        url="http://example.com/u1",
        final_url="http://example.com/u1",
        status_code=200,
        content_type="text/html",
        depth=1,
        parent_url=None,
        extracted=ExtractedData(
            page_type="unknown",
            internal_links=[]
        )
    )
    
    dataset = CrawlDataset(
        seed_url="http://example.com",
        crawled_at="2023-01-01T00:00:00Z",
        pages=[p1, p2, p3]
    )
    
    findings = rule.evaluate(dataset)
    assert len(findings) == 1
    assert findings[0].evidence.page == "http://example.com/a2"
    assert findings[0].severity == Severity.MEDIUM
    assert "no outbound internal navigation links" in findings[0].suggested_action.summary

def test_missing_image_alt_rule():
    rule = MissingImageAltRule()
    
    # 5 images + 5 valid alts → no finding
    p1 = PageRecord(
        url="http://example.com/p1",
        final_url="http://example.com/p1",
        status_code=200,
        content_type="text/html",
        depth=1,
        parent_url=None,
        extracted=ExtractedData(
            image_urls=["1.jpg", "2.jpg", "3.jpg", "4.jpg", "5.jpg"],
            image_alts=["a", "b", "c", "d", "e"]
        )
    )
    
    # 5 images + 3 valid alts → finding
    p2 = PageRecord(
        url="http://example.com/p2",
        final_url="http://example.com/p2",
        status_code=200,
        content_type="text/html",
        depth=1,
        parent_url=None,
        extracted=ExtractedData(
            image_urls=["1.jpg", "2.jpg", "3.jpg", "4.jpg", "5.jpg"],
            image_alts=["a", "b", "c"]
        )
    )
    
    # 5 images + 0 valid alts → finding
    p3 = PageRecord(
        url="http://example.com/p3",
        final_url="http://example.com/p3",
        status_code=200,
        content_type="text/html",
        depth=1,
        parent_url=None,
        extracted=ExtractedData(
            image_urls=["1.jpg", "2.jpg", "3.jpg", "4.jpg", "5.jpg"],
            image_alts=[]
        )
    )
    
    # whitespace-only alt → treated as missing
    p4 = PageRecord(
        url="http://example.com/p4",
        final_url="http://example.com/p4",
        status_code=200,
        content_type="text/html",
        depth=1,
        parent_url=None,
        extracted=ExtractedData(
            image_urls=["1.jpg"],
            image_alts=["   "]
        )
    )
    
    # missing alt attribute entirely → treated as missing (alts length is 0)
    p5 = PageRecord(
        url="http://example.com/p5",
        final_url="http://example.com/p5",
        status_code=200,
        content_type="text/html",
        depth=1,
        parent_url=None,
        extracted=ExtractedData(
            image_urls=["1.jpg"],
            image_alts=[]
        )
    )
    
    dataset = CrawlDataset(
        seed_url="http://example.com",
        crawled_at="2023-01-01T00:00:00Z",
        pages=[p1, p2, p3, p4, p5]
    )
    
    findings = rule.evaluate(dataset)
    assert len(findings) == 4
    
    urls = [f.evidence.page for f in findings]
    assert "http://example.com/p2" in urls
    assert "http://example.com/p3" in urls
    assert "http://example.com/p4" in urls
    assert "http://example.com/p5" in urls
    
    for f in findings:
        assert f.severity == Severity.MEDIUM
        assert f.suggested_action.summary == "Images are missing alternative text."
