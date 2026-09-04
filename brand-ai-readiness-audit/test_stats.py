import scrapy
from scrapy.crawler import CrawlerProcess

class MySpider(scrapy.Spider):
    name = 'myspider'
    start_urls = ['http://127.0.0.1:5003/']
    
    def parse(self, response):
        yield {'url': response.url}

process = CrawlerProcess()
process.crawl(MySpider)
process.start()

print(list(process.crawlers)[0].stats.get_stats())
