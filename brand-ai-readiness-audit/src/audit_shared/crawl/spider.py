import scrapy
import json
from urllib.parse import urlparse, urldefrag
from audit_shared.crawl.items import CrawlResultItem

class AuditSpider(scrapy.Spider):
    name = "audit_spider"

    def __init__(self, target_url, allowed_domains_list, max_depth=None, *args, **kwargs):
        super(AuditSpider, self).__init__(*args, **kwargs)
        self.start_urls = [target_url]
        self.allowed_domains = allowed_domains_list
        self.max_depth = max_depth
        self.seen_urls = set()
        
        # Normalize the seed domain if not provided explicitly
        if not self.allowed_domains:
            parsed = urlparse(target_url)
            self.allowed_domains = [parsed.hostname]

    def start_requests(self):
        for url in self.start_urls:
            self.seen_urls.add(url)
            self.crawler.stats.inc_value('audit/urls_discovered', 1)
            yield scrapy.Request(url, callback=self.parse, meta={'parent_url': None, 'depth': 0})

    def parse(self, response):
        final_url = response.url
        status_code = response.status
        content_type = response.headers.get('Content-Type', b'').decode('utf-8').lower()

        item = CrawlResultItem()
        redirect_urls = response.meta.get('redirect_urls', [])
        if redirect_urls:
            item['url'] = redirect_urls[0]
        else:
            item['url'] = response.request.url
            
        item['final_url'] = final_url
        item['status_code'] = status_code
        item['content_type'] = content_type
        item['depth'] = response.meta.get('depth', 0)
        item['parent_url'] = response.meta.get('parent_url')
        item['redirect_chain'] = redirect_urls
        item['crawl_status'] = 'success'
        
        diagnostics = {
            'extraction_success': True,
            'extraction_errors': [],
            'malformed_jsonld_count': 0,
            'text_extraction_success': True,
            'html_size': len(response.body) if hasattr(response, 'body') else 0,
            'visible_text_length': 0
        }

        if 'text/html' not in content_type:
            item['raw_html'] = ""
            item['extracted_data'] = {}
            item['diagnostics'] = diagnostics
            yield item
            return

        item['raw_html'] = response.text
        
        extracted = {}
        try:
            extracted['title'] = response.xpath('//title/text()').get()
            extracted['meta_description'] = response.xpath('//meta[@name="description" or @property="og:description"]/@content').get()
            extracted['language'] = response.xpath('//html/@lang').get()
            
            extracted['h1s'] = response.xpath('//h1//text()').getall()
            extracted['h2s'] = response.xpath('//h2//text()').getall()
            extracted['h3s'] = response.xpath('//h3//text()').getall()
            extracted['headings'] = response.xpath('//*[self::h1 or self::h2 or self::h3 or self::h4 or self::h5 or self::h6]//text()').getall()
            
            # Links
            a_tags = response.xpath('//a')
            internal_links = set()
            external_links = set()
            detailed_internal = []
            detailed_external = []
            
            for a in a_tags:
                href = a.xpath('@href').get()
                text = " ".join(a.xpath('.//text()').getall()).strip()
                if not href or href.startswith(('javascript:', 'mailto:', 'tel:', 'data:')):
                    continue
                    
                abs_url = response.urljoin(href)
                parsed = urlparse(abs_url)
                if parsed.scheme not in ('http', 'https'):
                    continue
                    
                clean_url, _ = urldefrag(abs_url)
                is_internal = any(parsed.hostname == domain or (parsed.hostname and parsed.hostname.endswith('.' + domain)) for domain in self.allowed_domains)
                
                link_obj = {'url': clean_url, 'text': text}
                if is_internal:
                    internal_links.add(clean_url)
                    detailed_internal.append(link_obj)
                else:
                    external_links.add(clean_url)
                    detailed_external.append(link_obj)
                    
            extracted['internal_links'] = list(internal_links)
            extracted['external_links'] = list(external_links)
            extracted['detailed_internal_links'] = detailed_internal
            extracted['detailed_external_links'] = detailed_external
            
            extracted['image_urls'] = response.xpath('//img/@src').getall()
            extracted['image_alts'] = response.xpath('//img/@alt').getall()
            extracted['canonical'] = response.xpath('//link[@rel="canonical"]/@href').get()
            extracted['meta_robots'] = response.xpath('//meta[@name="robots"]/@content').getall()
            
            # JSON-LD
            json_ld_scripts = response.xpath('//script[@type="application/ld+json"]/text()').getall()
            extracted['json_ld'] = json_ld_scripts
            parsed_json_ld = []
            for script in json_ld_scripts:
                try:
                    data = json.loads(script)
                    if isinstance(data, list):
                        parsed_json_ld.extend(data)
                    elif isinstance(data, dict):
                        if '@graph' in data and isinstance(data['@graph'], list):
                            parsed_json_ld.extend(data['@graph'])
                        else:
                            parsed_json_ld.append(data)
                except json.JSONDecodeError:
                    diagnostics['malformed_jsonld_count'] += 1
            extracted['parsed_json_ld'] = parsed_json_ld
            
            # Social / Metadata
            extracted['og_tags'] = response.xpath('//meta[starts-with(@property, "og:")]').getall()
            extracted['twitter_metadata'] = response.xpath('//meta[starts-with(@name, "twitter:")]').getall()
            
            # Date Candidates
            dates = []
            # Check meta
            published = response.xpath('//meta[@property="article:published_time"]/@content').get()
            if published:
                dates.append({'value': published, 'source': 'meta', 'field': 'article:published_time'})
            modified = response.xpath('//meta[@property="article:modified_time"]/@content').get()
            if modified:
                dates.append({'value': modified, 'source': 'meta', 'field': 'article:modified_time'})
                
            # Check JSON-LD for dates
            for p in parsed_json_ld:
                if isinstance(p, dict):
                    for date_field in ['datePublished', 'dateModified', 'uploadDate']:
                        if date_field in p:
                            val = p[date_field]
                            if isinstance(val, str):
                                dates.append({'value': val, 'source': 'json_ld', 'field': date_field})
            extracted['date_candidates'] = dates
            
            # Visible Text
            text_nodes = response.xpath('//body//text()[not(ancestor::script) and not(ancestor::style)]').getall()
            visible_text = " ".join([t.strip() for t in text_nodes if t.strip()])
            extracted['visible_text'] = visible_text
            diagnostics['visible_text_length'] = len(visible_text)
            
            # Page Type Signal (Deterministic)
            page_type = "unknown"
            if urlparse(final_url).path in ('', '/'):
                page_type = "homepage"
            elif '/product/' in final_url or '/p/' in final_url:
                page_type = "product"
            elif '/about' in final_url:
                page_type = "about"
            elif '/contact' in final_url:
                page_type = "contact"
            else:
                for p in parsed_json_ld:
                    if isinstance(p, dict) and p.get('@type') in ('Article', 'NewsArticle', 'BlogPosting'):
                        page_type = "article"
                        break
                    if isinstance(p, dict) and p.get('@type') == 'Product':
                        page_type = "product"
                        break
            extracted['page_type'] = page_type
            
        except Exception as e:
            diagnostics['extraction_success'] = False
            diagnostics['extraction_errors'].append(str(e))
            
        item['extracted_data'] = extracted
        item['diagnostics'] = diagnostics
        yield item
        
        if self.max_depth is not None and item['depth'] >= self.max_depth:
            return
        
        # Enqueue internal links safely
        for link in extracted.get('internal_links', []):
            if link not in self.seen_urls:
                self.seen_urls.add(link)
                self.crawler.stats.inc_value('audit/urls_discovered', 1)
            yield scrapy.Request(
                url=link, 
                callback=self.parse, 
                meta={'parent_url': final_url}
            )
