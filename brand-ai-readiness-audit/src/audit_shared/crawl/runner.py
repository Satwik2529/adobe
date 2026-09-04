import logging
from datetime import datetime
from scrapy.crawler import CrawlerProcess
from audit_shared.crawl.spider import AuditSpider
from audit_shared.config.settings import CrawlSettings
from audit_shared.models.data_flow import (
    CrawlDataset, PageRecord, ExtractedData, ExtractionDiagnostics, CrawlDiagnostics, CrawlStats, DateCandidate
)
from dataclasses import asdict
from scrapy.exceptions import IgnoreRequest

class BlockedUrlMiddleware:
    def process_exception(self, request, exception, spider):
        if isinstance(exception, IgnoreRequest):
            if not hasattr(spider, 'unfetched'):
                spider.unfetched = []
            spider.unfetched.append({"url": request.url, "reason": "robots_blocked"})
        return None

# Suppress overly verbose Scrapy logs
logging.getLogger('scrapy').setLevel(logging.WARNING)

def run_crawl(url: str, config: CrawlSettings) -> dict:
    """
    Runs the Scrapy crawler for the given URL and configuration.
    Returns a dictionary matching the CrawlDataset schema.
    """
    settings = {
        'USER_AGENT': 'Brand AI Readiness Audit (+http://example.com)',
        'ROBOTSTXT_OBEY': config.respect_robots_txt,
        'DEPTH_LIMIT': config.crawl_depth,
        'CLOSESPIDER_PAGECOUNT': config.page_limit,
        'CONCURRENT_REQUESTS': config.concurrency,
        'DOWNLOAD_TIMEOUT': config.request_timeout,
        'RETRY_ENABLED': True,
        'RETRY_TIMES': 2,
        'DOWNLOADER_MIDDLEWARES': {
            'audit_shared.crawl.runner.BlockedUrlMiddleware': 50,
        },
        'ITEM_PIPELINES': {
            'audit_shared.crawl.pipelines.MemoryPipeline': 100,
        },
        'LOG_LEVEL': 'WARNING',
        'HTTPERROR_ALLOW_ALL': True,
        'REDIRECT_ENABLED': True,
    }

    from audit_shared.crawl.pipelines import MemoryPipeline
    MemoryPipeline.results = []
    
    process = CrawlerProcess(settings)
    process.crawl(AuditSpider, target_url=url, allowed_domains_list=config.allowed_domains, max_depth=config.crawl_depth)
    crawler = list(process.crawlers)[0]
    process.start()
    
    unfetched_urls = getattr(crawler.spider, 'unfetched', [])
    
    results = MemoryPipeline.results
    raw_stats = crawler.stats.get_stats()
    
    # Process pages to PageRecord
    pages = []
    html_pages_crawled = 0
    successful_pages = 0
    failed_pages = 0
    non_html_responses = 0
    
    for r in results:
        is_html = 'text/html' in r.get('content_type', '')
        status = r.get('status_code', 0)
        
        if is_html:
            html_pages_crawled += 1
            if status < 400:
                successful_pages += 1
            else:
                failed_pages += 1
        else:
            non_html_responses += 1

        ext = r.get('extracted_data', {})
        diag = r.get('diagnostics', {})
        
        extracted = ExtractedData(
            title=ext.get('title'),
            meta_description=ext.get('meta_description'),
            meta_robots=ext.get('meta_robots', []),
            language=ext.get('language'),
            visible_text=ext.get('visible_text', ''),
            h1s=ext.get('h1s', []),
            h2s=ext.get('h2s', []),
            h3s=ext.get('h3s', []),
            headings=ext.get('headings', []),
            internal_links=ext.get('internal_links', []),
            external_links=ext.get('external_links', []),
            detailed_internal_links=ext.get('detailed_internal_links', []),
            detailed_external_links=ext.get('detailed_external_links', []),
            image_urls=ext.get('image_urls', []),
            image_alts=ext.get('image_alts', []),
            canonical=ext.get('canonical'),
            json_ld=ext.get('json_ld', []),
            parsed_json_ld=ext.get('parsed_json_ld', []),
            og_tags=ext.get('og_tags', []),
            twitter_metadata=ext.get('twitter_metadata', []),
            date_candidates=[DateCandidate(**dc) for dc in ext.get('date_candidates', [])],
            page_type=ext.get('page_type', 'unknown')
        )
        
        diagnostics = ExtractionDiagnostics(
            extraction_success=diag.get('extraction_success', True),
            extraction_errors=diag.get('extraction_errors', []),
            malformed_jsonld_count=diag.get('malformed_jsonld_count', 0),
            text_extraction_success=diag.get('text_extraction_success', True),
            html_size=diag.get('html_size', 0),
            visible_text_length=diag.get('visible_text_length', 0)
        )
        
        pr = PageRecord(
            url=r['url'],
            final_url=r.get('final_url', ''),
            status_code=status,
            content_type=r.get('content_type', ''),
            depth=r.get('depth', 0),
            parent_url=r.get('parent_url'),
            redirect_chain=r.get('redirect_chain', []),
            crawl_status=r.get('crawl_status', 'success'),
            raw_html=r.get('raw_html', ''),
            extracted=extracted,
            diagnostics=diagnostics
        )
        pages.append(pr)

    redirects = raw_stats.get('downloader/response_status_count/301', 0) + raw_stats.get('downloader/response_status_count/302', 0)
    
    crawl_stats = CrawlStats(
        urls_discovered=raw_stats.get('audit/urls_discovered', 1), # default 1 for seed
        urls_scheduled=raw_stats.get('scheduler/enqueued', 1),
        requests_attempted=raw_stats.get('downloader/request_count', 0),
        responses_received=raw_stats.get('response_received_count', 0),
        html_pages_crawled=html_pages_crawled,
        successful_pages=successful_pages,
        failed_pages=failed_pages,
        robots_blocked=raw_stats.get('robotstxt/forbidden', 0),
        duplicate_urls=raw_stats.get('dupefilter/filtered', 0),
        redirects=redirects,
        non_html_responses=non_html_responses,
        crawl_duration=raw_stats.get('elapsed_time_seconds', 0.0)
    )
    
    robots_status = None
    for k, v in raw_stats.items():
        if k.startswith('robotstxt/response_status_count/'):
            robots_status = int(k.split('/')[-1])
            break

    crawl_diagnostics = CrawlDiagnostics(
        robots_txt_fetched=raw_stats.get('downloader/request_method_count/GET', 0) > raw_stats.get('response_received_count', 0) or robots_status is not None,
        robots_txt_status=robots_status,
        crawl_errors=[],
        request_failures=0,
        extraction_failures=0,
        pages_discovered_not_fetched=0,
        robots_blocked_urls=raw_stats.get('robotstxt/forbidden', 0),
        crawl_termination_reason=raw_stats.get('finish_reason', 'finished'),
        configured_depth_limit=config.crawl_depth or 0,
        configured_page_limit=config.page_limit or 0
    )
    
    safe_raw_stats = {}
    for k, v in raw_stats.items():
        if isinstance(v, datetime):
            safe_raw_stats[k] = v.isoformat()
        else:
            safe_raw_stats[k] = v
            
    dataset = CrawlDataset(
        seed_url=url,
        crawled_at=datetime.utcnow().isoformat(),
        pages=pages,
        crawl_stats=crawl_stats,
        crawl_diagnostics=crawl_diagnostics,
        raw_scrapy_stats=safe_raw_stats,
        unfetched_urls=unfetched_urls
    )
    
    return asdict(dataset)

if __name__ == "__main__":
    config = CrawlSettings(target_url="http://quotes.toscrape.com/", page_limit=5)
    data = run_crawl("http://quotes.toscrape.com/", config)
    print(f"Crawled {len(data['pages'])} pages.")
