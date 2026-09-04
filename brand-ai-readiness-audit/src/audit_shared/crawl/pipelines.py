class MemoryPipeline:
    """
    Pipeline to store all CrawlResultItem in memory
    so they can be returned after the crawl finishes.
    """
    results = []
    
    def process_item(self, item, **kwargs):
        # Convert Item to dict for easier downstream usage
        MemoryPipeline.results.append(dict(item))
        return item
