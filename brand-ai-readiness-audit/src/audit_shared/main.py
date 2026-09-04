"""
Audit Orchestrator Entrypoint Foundation.
"""

from audit_shared.config.settings import load_config
from audit_shared.logging.logger import logger

def run_audit(target_url: str):
    """
    Entrypoint for the AI Readiness Audit.
    For Phase 1, it runs the crawler.
    """
    config = load_config()
    config.crawl.target_url = target_url
    
    logger.info(f"Initializing AI Readiness Audit for {target_url}")
    logger.info("NOTE: Extraction is basic. NLP and GenAI are NOT yet implemented (Phase 1).")
    
    from audit_shared.crawl.runner import run_crawl
    logger.info("Starting crawler...")
    data = run_crawl(target_url, config.crawl)
    
    logger.info(f"Crawl finished. Found {len(data['results'])} pages.")
    
    logger.info("Audit foundation initialized successfully.")
    return data

if __name__ == "__main__":
    # Minimal CLI placeholder
    import sys
    import json
    if len(sys.argv) > 1:
        data = run_audit(sys.argv[1])
        # optionally save to a file
        with open("smoke_test_results.json", "w") as f:
            json.dump(data, f, indent=2)
    else:
        print("Usage: python main.py <URL>")

