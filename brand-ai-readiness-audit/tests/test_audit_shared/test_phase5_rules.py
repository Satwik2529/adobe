import pytest
import hashlib
from typing import List, Dict, Any
from audit_shared.models.data_flow import (
    CrawlDataset, PageRecord, ExtractedData, ExtractionDiagnostics,
    CrawlDiagnostics, CrawlStats, DateCandidate
)
from audit_shared.rules.ai_discoverability import (
    ClientErrorRule, ServerErrorRule, RobotsBlockingRule, NoindexRule, NofollowRule,
    RedirectChainRule, MissingCanonicalRule, CanonicalToErrorRule, CanonicalToRedirectRule,
    BrokenInternalLinkRule, InternalLinkToRedirectRule, OrphanPageRule, ExcessiveDepthRule,
    MissingH1Rule, MissingTitleRule, EmptyTitleRule, MissingMetaDescriptionRule,
    MalformedJsonLdRule, ExactDuplicateContentRule, ThinContentRule
)
from audit_shared.validation.finding_validator import FindingValidator

# Helper to create a dummy dataset
def mock_dataset(pages: List[PageRecord], unfetched_urls: List[Dict[str, str]] = None, diagnostics: CrawlDiagnostics = None) -> CrawlDataset:
    if unfetched_urls is None:
        unfetched_urls = []
    if diagnostics is None:
        diagnostics = CrawlDiagnostics(crawl_termination_reason="finished", pages_discovered_not_fetched=len(unfetched_urls))
    return CrawlDataset(
        seed_url="https://example.com",
        crawled_at="2024-01-01T00:00:00Z",
        crawl_stats=CrawlStats(),
        crawl_diagnostics=diagnostics,
        pages=pages,
        unfetched_urls=unfetched_urls
    )

def mock_page(
    url: str,
    status_code: int = 200,
    content_type: str = "text/html",
    depth: int = 1,
    redirect_chain: List[str] = None,
    visible_text: str = "Some normal visible text with enough length to pass thin content",
    h1s: List[str] = None,
    title: str = "Valid Title",
    meta_description: str = "Valid description",
    canonical: str = None,
    meta_robots: List[str] = None,
    internal_links: List[str] = None,
    malformed_jsonld_count: int = 0
) -> PageRecord:
    ext = ExtractedData(
        title=title,
        meta_description=meta_description,
        h1s=h1s if h1s is not None else ["Valid H1"],
        canonical=canonical,
        meta_robots=meta_robots or [],
        visible_text=visible_text,
        internal_links=internal_links or []
    )
    diag = ExtractionDiagnostics(
        malformed_jsonld_count=malformed_jsonld_count,
        visible_text_length=len(visible_text) if visible_text else 0
    )
    return PageRecord(
        url=url,
        final_url=url,
        status_code=status_code,
        content_type=content_type,
        depth=depth,
        redirect_chain=redirect_chain or [],
        parent_url="https://example.com" if url != "https://example.com" else None,
        crawl_status="success",
        raw_html="<html></html>",
        extracted=ext,
        diagnostics=diag
    )

def assert_valid_finding(finding, dataset):
    validator = FindingValidator()
    validator.validate(finding, dataset)

def test_client_error_rule():
    rule = ClientErrorRule()
    # Positive
    ds = mock_dataset([mock_page("https://example.com/404", status_code=404)])
    findings = rule.evaluate(ds)
    assert len(findings) == 1
    assert findings[0].evidence.observed_value == "404"
    assert_valid_finding(findings[0], ds)
    
    # Negative
    ds_neg = mock_dataset([mock_page("https://example.com/200", status_code=200)])
    assert len(rule.evaluate(ds_neg)) == 0

    # Must-not-trigger / Boundary (Non-HTML)
    ds_boundary = mock_dataset([mock_page("https://example.com/img.png", status_code=404, content_type="image/png")])
    assert len(rule.evaluate(ds_boundary)) == 0

def test_server_error_rule():
    rule = ServerErrorRule()
    # Positive
    ds = mock_dataset([mock_page("https://example.com/500", status_code=500)])
    findings = rule.evaluate(ds)
    assert len(findings) == 1
    assert findings[0].evidence.observed_value == "500"
    assert_valid_finding(findings[0], ds)
    
    # Negative
    ds_neg = mock_dataset([mock_page("https://example.com/200", status_code=200)])
    assert len(rule.evaluate(ds_neg)) == 0
    
    # Must-not-trigger / Boundary (Non-HTML)
    ds_boundary = mock_dataset([mock_page("https://example.com/img.png", status_code=500, content_type="image/png")])
    assert len(rule.evaluate(ds_boundary)) == 0

def test_robots_blocked_rule():
    rule = RobotsBlockingRule()
    ds = mock_dataset(
        pages=[mock_page("https://example.com")],
        unfetched_urls=[{"url": "https://example.com/private", "reason": "robots_blocked"}]
    )
    findings = rule.evaluate(ds)
    assert len(findings) == 1
    assert findings[0].evidence.page == "https://example.com" # Provenance anchoring
    assert "1 URLs blocked" in findings[0].evidence.observed_value
    assert_valid_finding(findings[0], ds)
    
    # Negative
    ds_empty = mock_dataset(pages=[mock_page("https://example.com")])
    assert len(rule.evaluate(ds_empty)) == 0
    
    # Must-not-trigger (Other drop reasons)
    ds_other = mock_dataset(
        pages=[mock_page("https://example.com")],
        unfetched_urls=[{"url": "https://example.com/external", "reason": "offsite"}]
    )
    assert len(rule.evaluate(ds_other)) == 0

def test_noindex_rule():
    rule = NoindexRule()
    ds = mock_dataset([mock_page("https://example.com/noindex", meta_robots=["noindex", "nofollow"])])
    findings = rule.evaluate(ds)
    assert len(findings) == 1
    assert_valid_finding(findings[0], ds)
    
    ds_neg = mock_dataset([mock_page("https://example.com/ok", meta_robots=["index", "follow"])])
    assert len(rule.evaluate(ds_neg)) == 0
    
    ds_empty = mock_dataset([mock_page("https://example.com/ok", meta_robots=[])])
    assert len(rule.evaluate(ds_empty)) == 0

def test_nofollow_rule():
    rule = NofollowRule()
    ds = mock_dataset([mock_page("https://example.com/nofollow", meta_robots=["index", "nofollow"])])
    findings = rule.evaluate(ds)
    assert len(findings) == 1
    assert_valid_finding(findings[0], ds)
    
    ds_neg = mock_dataset([mock_page("https://example.com/ok", meta_robots=["index", "follow"])])
    assert len(rule.evaluate(ds_neg)) == 0
    
    ds_empty = mock_dataset([mock_page("https://example.com/ok", meta_robots=[])])
    assert len(rule.evaluate(ds_empty)) == 0

def test_redirect_chain_rule():
    rule = RedirectChainRule()
    ds = mock_dataset([mock_page("https://example.com/dest", redirect_chain=["https://example.com/1", "https://example.com/2"])])
    findings = rule.evaluate(ds)
    assert len(findings) == 1
    assert_valid_finding(findings[0], ds)
    
    # Negative (Single redirect)
    ds_neg = mock_dataset([mock_page("https://example.com/dest", redirect_chain=["https://example.com/1"])])
    assert len(rule.evaluate(ds_neg)) == 0
    
    # Boundary (No redirects)
    ds_boundary = mock_dataset([mock_page("https://example.com/dest", redirect_chain=[])])
    assert len(rule.evaluate(ds_boundary)) == 0

def test_missing_canonical_rule():
    rule = MissingCanonicalRule()
    ds = mock_dataset([mock_page("https://example.com/nocanon", canonical=None)])
    findings = rule.evaluate(ds)
    assert len(findings) == 1
    assert_valid_finding(findings[0], ds)
    
    ds_neg = mock_dataset([mock_page("https://example.com/yescanon", canonical="https://example.com/yescanon")])
    assert len(rule.evaluate(ds_neg)) == 0
    
    # Boundary: 404 should not trigger missing canonical
    ds_404 = mock_dataset([mock_page("https://example.com/404", canonical=None, status_code=404)])
    assert len(rule.evaluate(ds_404)) == 0

def test_canonical_to_error_rule():
    rule = CanonicalToErrorRule()
    ds = mock_dataset([
        mock_page("https://example.com/1", canonical="https://example.com/404"),
        mock_page("https://example.com/404", status_code=404)
    ])
    findings = rule.evaluate(ds)
    assert len(findings) == 1
    assert findings[0].evidence.observed_value == "https://example.com/404"
    assert_valid_finding(findings[0], ds)
    
    # Negative: Canonical is 200
    ds_neg = mock_dataset([
        mock_page("https://example.com/1", canonical="https://example.com/200"),
        mock_page("https://example.com/200", status_code=200)
    ])
    assert len(rule.evaluate(ds_neg)) == 0
    
    # Must-not-trigger: Canonical not crawled
    ds_not_crawled = mock_dataset([mock_page("https://example.com/1", canonical="https://example.com/not_crawled")])
    assert len(rule.evaluate(ds_not_crawled)) == 0

def test_canonical_to_redirect_rule():
    rule = CanonicalToRedirectRule()
    ds = mock_dataset([
        mock_page("https://example.com/1", canonical="https://example.com/redir"),
        mock_page("https://example.com/redir", redirect_chain=["https://example.com/old"])
    ])
    findings = rule.evaluate(ds)
    assert len(findings) == 1
    assert_valid_finding(findings[0], ds)
    
    # Negative: Canonical is 200 directly
    ds_neg = mock_dataset([
        mock_page("https://example.com/1", canonical="https://example.com/ok"),
        mock_page("https://example.com/ok")
    ])
    assert len(rule.evaluate(ds_neg)) == 0

def test_broken_internal_link_rule():
    rule = BrokenInternalLinkRule()
    ds = mock_dataset([
        mock_page("https://example.com/1", internal_links=["https://example.com/404"]),
        mock_page("https://example.com/404", status_code=404)
    ])
    findings = rule.evaluate(ds)
    assert len(findings) == 1
    assert "https://example.com/404" in findings[0].evidence.observed_value
    assert_valid_finding(findings[0], ds)
    
    # Negative: Link is 200
    ds_neg = mock_dataset([
        mock_page("https://example.com/1", internal_links=["https://example.com/200"]),
        mock_page("https://example.com/200", status_code=200)
    ])
    assert len(rule.evaluate(ds_neg)) == 0

def test_internal_link_to_redirect_rule():
    rule = InternalLinkToRedirectRule()
    ds = mock_dataset([
        mock_page("https://example.com/1", internal_links=["https://example.com/redir"]),
        mock_page("https://example.com/redir", redirect_chain=["https://example.com/old"])
    ])
    findings = rule.evaluate(ds)
    assert len(findings) == 1
    assert_valid_finding(findings[0], ds)
    
    # Negative: Link is 200 directly
    ds_neg = mock_dataset([
        mock_page("https://example.com/1", internal_links=["https://example.com/ok"]),
        mock_page("https://example.com/ok")
    ])
    assert len(rule.evaluate(ds_neg)) == 0

def test_orphan_page_rule():
    rule = OrphanPageRule()
    p1 = mock_page("https://example.com", depth=0, internal_links=[])
    p2 = mock_page("https://example.com/orphan", depth=1, internal_links=[])
    ds = mock_dataset([p1, p2])
    
    findings = rule.evaluate(ds)
    assert len(findings) == 1
    assert findings[0].evidence.page == "https://example.com/orphan"
    assert_valid_finding(findings[0], ds)
    
    # Negative
    p1_neg = mock_page("https://example.com", depth=0, internal_links=["https://example.com/linked"])
    p2_neg = mock_page("https://example.com/linked", depth=1, internal_links=[])
    ds_neg = mock_dataset([p1_neg, p2_neg])
    assert len(rule.evaluate(ds_neg)) == 0
    
    # Boundary: incomplete crawl suppression
    ds_inc = mock_dataset([p1, p2], diagnostics=CrawlDiagnostics(crawl_termination_reason="timeout", pages_discovered_not_fetched=1))
    assert len(rule.evaluate(ds_inc)) == 0

def test_excessive_crawl_depth_rule():
    rule = ExcessiveDepthRule()
    ds = mock_dataset([mock_page("https://example.com/deep", depth=4)])
    findings = rule.evaluate(ds)
    assert len(findings) == 1
    assert_valid_finding(findings[0], ds)
    
    # Negative
    ds_neg = mock_dataset([mock_page("https://example.com/shallow", depth=3)])
    assert len(rule.evaluate(ds_neg)) == 0

def test_missing_h1_rule():
    rule = MissingH1Rule()
    ds = mock_dataset([mock_page("https://example.com/noh1", h1s=[])])
    findings = rule.evaluate(ds)
    assert len(findings) == 1
    assert_valid_finding(findings[0], ds)
    
    # Negative
    ds_neg = mock_dataset([mock_page("https://example.com/yesh1", h1s=["H1"])])
    assert len(rule.evaluate(ds_neg)) == 0

def test_missing_title_rule():
    rule = MissingTitleRule()
    ds = mock_dataset([mock_page("https://example.com/notitle", title=None)])
    findings = rule.evaluate(ds)
    assert len(findings) == 1
    assert_valid_finding(findings[0], ds)
    
    # Negative (Empty title is NOT missing, handled by EmptyTitleRule)
    ds_empty = mock_dataset([mock_page("https://example.com/emptytitle", title="")])
    assert len(rule.evaluate(ds_empty)) == 0

def test_empty_title_rule():
    rule = EmptyTitleRule()
    ds = mock_dataset([mock_page("https://example.com/emptytitle", title="   ")])
    findings = rule.evaluate(ds)
    assert len(findings) == 1
    assert_valid_finding(findings[0], ds)
    
    # Negative (Missing title should not trigger this rule)
    ds_missing = mock_dataset([mock_page("https://example.com/notitle", title=None)])
    assert len(rule.evaluate(ds_missing)) == 0

def test_missing_meta_desc_rule():
    rule = MissingMetaDescriptionRule()
    ds = mock_dataset([mock_page("https://example.com/nodesc", meta_description="")])
    findings = rule.evaluate(ds)
    assert len(findings) == 1
    assert_valid_finding(findings[0], ds)
    
    ds_neg = mock_dataset([mock_page("https://example.com/yesdesc", meta_description="Yes")])
    assert len(rule.evaluate(ds_neg)) == 0

def test_malformed_json_ld_rule():
    rule = MalformedJsonLdRule()
    ds = mock_dataset([mock_page("https://example.com/badjson", malformed_jsonld_count=1)])
    findings = rule.evaluate(ds)
    assert len(findings) == 1
    assert_valid_finding(findings[0], ds)
    
    # Negative
    ds_neg = mock_dataset([mock_page("https://example.com/goodjson", malformed_jsonld_count=0)])
    assert len(rule.evaluate(ds_neg)) == 0

def test_exact_duplicate_content_rule():
    rule = ExactDuplicateContentRule()
    ds = mock_dataset([
        mock_page("https://example.com/1", visible_text="Duplicate Text"),
        mock_page("https://example.com/2", visible_text="Duplicate Text\n "),
        mock_page("https://example.com/3", visible_text="Unique Text")
    ])
    findings = rule.evaluate(ds)
    assert len(findings) == 1
    assert findings[0].evidence.pages_affected == 2
    assert "https://example.com/1" in findings[0].evidence.affected_pages.sample
    assert "https://example.com/2" in findings[0].evidence.affected_pages.sample
    assert "https://example.com/3" not in findings[0].evidence.affected_pages.sample
    assert_valid_finding(findings[0], ds)
    
    # Boundary: Ensure zero-length text is excluded
    ds_boundary = mock_dataset([
        mock_page("https://example.com/4", visible_text="  \n "),
        mock_page("https://example.com/5", visible_text="")
    ])
    assert len(rule.evaluate(ds_boundary)) == 0
    
    # Must-not-trigger: 404 pages with same text
    ds_404 = mock_dataset([
        mock_page("https://example.com/6", visible_text="Not Found", status_code=404),
        mock_page("https://example.com/7", visible_text="Not Found", status_code=404)
    ])
    assert len(rule.evaluate(ds_404)) == 0

def test_thin_content_rule():
    rule = ThinContentRule()
    ds = mock_dataset([mock_page("https://example.com/thin", visible_text="short")])
    findings = rule.evaluate(ds)
    assert len(findings) == 1
    assert_valid_finding(findings[0], ds)
    
    ds_neg = mock_dataset([mock_page("https://example.com/notthin", visible_text="long " * 20)])
    assert len(rule.evaluate(ds_neg)) == 0
