"""
Data flow contract interfaces for the Audit pipelines.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

@dataclass
class CrawlStats:
    urls_discovered: int = 0
    urls_scheduled: int = 0
    requests_attempted: int = 0
    responses_received: int = 0
    html_pages_crawled: int = 0
    successful_pages: int = 0
    failed_pages: int = 0
    robots_blocked: int = 0
    duplicate_urls: int = 0
    redirects: int = 0
    non_html_responses: int = 0
    crawl_duration: float = 0.0

@dataclass
class DateCandidate:
    value: str
    source: str
    field: str

@dataclass
class ExtractedData:
    title: Optional[str] = None
    meta_description: Optional[str] = None
    meta_robots: List[str] = field(default_factory=list)
    language: Optional[str] = None
    visible_text: str = ""
    
    h1s: List[str] = field(default_factory=list)
    h2s: List[str] = field(default_factory=list)
    h3s: List[str] = field(default_factory=list)
    headings: List[str] = field(default_factory=list)
    
    internal_links: List[str] = field(default_factory=list)
    external_links: List[str] = field(default_factory=list)
    # We could store detailed links, but for now we store raw strings to keep backward compatibility
    # and maybe a separate structure for anchors.
    # We will just add anchor_texts as a generic list for now, or detailed links.
    detailed_internal_links: List[Dict[str, str]] = field(default_factory=list)
    detailed_external_links: List[Dict[str, str]] = field(default_factory=list)
    
    image_urls: List[str] = field(default_factory=list)
    image_alts: List[str] = field(default_factory=list)
    
    canonical: Optional[str] = None
    
    json_ld: List[str] = field(default_factory=list)
    parsed_json_ld: List[Dict[str, Any]] = field(default_factory=list)
    
    og_tags: List[str] = field(default_factory=list)
    twitter_metadata: List[str] = field(default_factory=list)
    
    date_candidates: List[DateCandidate] = field(default_factory=list)
    page_type: str = "unknown"

@dataclass
class ExtractionDiagnostics:
    extraction_success: bool = True
    extraction_errors: List[str] = field(default_factory=list)
    malformed_jsonld_count: int = 0
    text_extraction_success: bool = True
    html_size: int = 0
    visible_text_length: int = 0

@dataclass
class PageRecord:
    url: str
    final_url: str
    status_code: int
    content_type: str
    depth: int
    parent_url: Optional[str]
    redirect_chain: List[str] = field(default_factory=list)
    crawl_status: str = "success"
    raw_html: str = ""
    extracted: ExtractedData = field(default_factory=ExtractedData)
    diagnostics: ExtractionDiagnostics = field(default_factory=ExtractionDiagnostics)

@dataclass
class CrawlDiagnostics:
    robots_txt_fetched: bool = False
    robots_txt_status: Optional[int] = None
    crawl_errors: List[str] = field(default_factory=list)
    request_failures: int = 0
    extraction_failures: int = 0
    pages_discovered_not_fetched: int = 0
    robots_blocked_urls: int = 0
    crawl_termination_reason: str = "finished"
    configured_depth_limit: int = 0
    configured_page_limit: int = 0

@dataclass
class CrawlDataset:
    seed_url: str
    crawled_at: str
    pages: List[PageRecord] = field(default_factory=list)
    crawl_stats: CrawlStats = field(default_factory=CrawlStats)
    crawl_diagnostics: CrawlDiagnostics = field(default_factory=CrawlDiagnostics)
    raw_scrapy_stats: Dict[str, Any] = field(default_factory=dict)
    
    # Track discovered but not fetched for downstream systems
    unfetched_urls: List[Dict[str, str]] = field(default_factory=list)

# Finding models have been moved to src/audit_shared/models/finding.py
