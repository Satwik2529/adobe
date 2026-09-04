"""
Basic configuration architecture for AI Readiness Audit.
"""

from typing import List, Optional
from dataclasses import dataclass, field

@dataclass
class CrawlSettings:
    target_url: str = ""
    allowed_domains: List[str] = field(default_factory=list)
    crawl_depth: int = 2
    page_limit: int = 100
    concurrency: int = 5
    request_timeout: int = 30
    respect_robots_txt: bool = True  # MUST ALWAYS BE TRUE OR ENFORCED

@dataclass
class AuditSettings:
    nlp_enabled: bool = False
    genai_enabled: bool = False
    genai_model: Optional[str] = None

@dataclass
class AppConfig:
    crawl: CrawlSettings = field(default_factory=CrawlSettings)
    audit: AuditSettings = field(default_factory=AuditSettings)
    output_location: str = "report.json"

def load_config() -> AppConfig:
    """
    Load the application configuration.
    Currently returns a default configuration for Phase 0.
    """
    return AppConfig()
