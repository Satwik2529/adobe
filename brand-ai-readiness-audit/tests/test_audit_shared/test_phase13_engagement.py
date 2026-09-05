import pytest
from typing import List

from audit_shared.models.data_flow import CrawlDataset, PageRecord, ExtractedData, ExtractionDiagnostics
from audit_shared.rules.engagement import DeadEndContentRule

def mock_dataset(pages: List[PageRecord]) -> CrawlDataset:
    return CrawlDataset(
        seed_url="https://example.com",
        crawled_at="2024-01-01T12:00:00Z",
        pages=pages
    )

def mock_page_engagement(url: str, internal_links: List[str], page_type: str = "article", status_code: int = 200) -> PageRecord:
    ext = ExtractedData(
        title="Test",
        meta_description="Test",
        h1s=["H1"],
        canonical=url,
        meta_robots=[],
        visible_text="Some text",
        internal_links=internal_links,
        page_type=page_type
    )
    return PageRecord(
        url=url,
        final_url=url,
        status_code=status_code,
        content_type="text/html",
        depth=1,
        redirect_chain=[],
        parent_url=None,
        crawl_status="success",
        raw_html="<html></html>",
        extracted=ext,
        diagnostics=ExtractionDiagnostics(malformed_jsonld_count=0, visible_text_length=10)
    )

def test_genuine_dead_end_content_page():
    # 200 article page with 0 valid outbound links
    page = mock_page_engagement("https://example.com/deadend", [], page_type="article")
    ds = mock_dataset([page])
    
    findings = DeadEndContentRule().evaluate(ds)
    assert len(findings) == 1
    assert findings[0].evidence.details["outbound_internal_link_count"] == 0

def test_genuine_dead_end_content_page_only_self_links():
    # 200 article page with only self-links (should be treated as 0 outbound)
    page = mock_page_engagement("https://example.com/deadend", [
        "https://example.com/deadend",
        "https://example.com/deadend#section1"
    ], page_type="article")
    ds = mock_dataset([page])
    
    findings = DeadEndContentRule().evaluate(ds)
    assert len(findings) == 1

def test_content_page_with_valid_internal_links():
    # 200 article page with valid internal links
    page = mock_page_engagement("https://example.com/valid", [
        "https://example.com/other-page"
    ], page_type="article")
    ds = mock_dataset([page])
    
    findings = DeadEndContentRule().evaluate(ds)
    assert len(findings) == 0

def test_utility_page_dead_end():
    # 200 utility/login page with 0 links -> should NOT trigger
    page = mock_page_engagement("https://example.com/login", [], page_type="utility")
    ds = mock_dataset([page])
    
    findings = DeadEndContentRule().evaluate(ds)
    assert len(findings) == 0

def test_error_page_dead_end():
    # 404 page (even if it's an article) -> should NOT trigger
    page = mock_page_engagement("https://example.com/404", [], page_type="article", status_code=404)
    ds = mock_dataset([page])
    
    findings = DeadEndContentRule().evaluate(ds)
    assert len(findings) == 0
