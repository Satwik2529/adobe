import scrapy
from typing import Dict, Any

class CrawlResultItem(scrapy.Item):
    """
    Scrapy Item mapping to the CrawlResult data contract.
    """
    url = scrapy.Field()
    final_url = scrapy.Field()
    status_code = scrapy.Field()
    content_type = scrapy.Field()
    depth = scrapy.Field()
    parent_url = scrapy.Field()
    raw_html = scrapy.Field()
    extracted_data = scrapy.Field()
    diagnostics = scrapy.Field()
    redirect_chain = scrapy.Field()
    crawl_status = scrapy.Field()
