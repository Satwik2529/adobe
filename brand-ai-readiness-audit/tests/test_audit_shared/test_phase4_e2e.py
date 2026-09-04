import pytest
import sys
import os
import json
import subprocess

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'crawler'))
from fixture_server import start_server

from typing import List
from audit_shared.models.finding import (
    Finding, Pipeline, Severity, Trigger, TriggerType, SuggestedAction, ActionPriority, Evidence, generate_finding_id
)
from audit_shared.models.data_flow import CrawlDataset, PageRecord, ExtractedData, CrawlStats, CrawlDiagnostics, ExtractionDiagnostics
from audit_shared.rules.base import AuditRule
from audit_shared.rules.registry import RuleRegistry
from audit_shared.rules.engine import RuleEngine
from audit_shared.rules.models import RuleExecutionStatus

@pytest.fixture(scope="module")
def local_server():
    server = start_server(port=5007)
    yield "http://127.0.0.1:5007"
    server.shutdown()

def run_crawler_subprocess(url, depth=10, limit=100):
    script_path = os.path.join(os.path.dirname(__file__), '..', 'crawler', 'run_crawler_subprocess.py')
    result = subprocess.run(
        [sys.executable, script_path, url, str(depth), str(limit)],
        capture_output=True, text=True, check=True,
        cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    )
    for line in result.stdout.splitlines():
        if line.startswith('{'):
            return json.loads(line)
    return {}

def hydrate_dataset(data: dict) -> CrawlDataset:
    pages = []
    for p in data.get('pages', []):
        ext = p.get('extracted', {})
        extracted = ExtractedData(**{k:v for k,v in ext.items() if k != 'date_candidates'})
        from audit_shared.models.data_flow import DateCandidate
        if 'date_candidates' in ext:
            extracted.date_candidates = [DateCandidate(**dc) for dc in ext['date_candidates']]
        
        diag_data = p.get('diagnostics', {})
        diagnostics = ExtractionDiagnostics(**diag_data)
        pages.append(PageRecord(
            url=p['url'],
            final_url=p['final_url'],
            status_code=p['status_code'],
            content_type=p['content_type'],
            depth=p['depth'],
            parent_url=p['parent_url'],
            redirect_chain=p.get('redirect_chain', []),
            crawl_status=p.get('crawl_status', 'success'),
            raw_html=p.get('raw_html', ''),
            extracted=extracted,
            diagnostics=diagnostics
        ))
    
    return CrawlDataset(
        seed_url=data.get('seed_url', ''),
        crawled_at=data.get('crawled_at', ''),
        pages=pages,
        crawl_stats=CrawlStats(**data.get('crawl_stats', {})),
        crawl_diagnostics=CrawlDiagnostics(**data.get('crawl_diagnostics', {})),
        raw_scrapy_stats=data.get('raw_scrapy_stats', {}),
        unfetched_urls=data.get('unfetched_urls', [])
    )

class E2EDummyRule(AuditRule):
    @property
    def rule_id(self) -> str: return "E2E-TEST-RULE"
    @property
    def pipeline(self) -> Pipeline: return Pipeline.AI_DISCOVERABILITY
    @property
    def description(self) -> str: return "Extracts title from /about"
    def evaluate(self, dataset: CrawlDataset) -> List[Finding]:
        about_page = next((p for p in dataset.pages if p.url.endswith('/about')), None)
        if not about_page:
            return []
            
        return [
            Finding(
                id=generate_finding_id(self.rule_id, [about_page.url]),
                pipeline=self.pipeline,
                title="E2E Finding",
                severity=Severity.HIGH,
                trigger=Trigger(rule_id=self.rule_id, type=TriggerType.DETERMINISTIC),
                suggested_action=SuggestedAction(summary="Fix", priority=ActionPriority.HIGH),
                evidence=Evidence(
                    page=about_page.url,
                    source="extracted",
                    field="title",
                    observed_value=about_page.extracted.title,
                    pages_checked=1,
                    pages_affected=1,
                    affected_percentage=100.0
                )
            )
        ]

def test_phase1_to_phase4_end_to_end(local_server):
    """
    Cumulative integration test proving Phase 1, Phase 2, Phase 3, and Phase 4 boundaries.
    """
    # 1. Phase 1 & 2: Run crawler
    raw_dict = run_crawler_subprocess(local_server + "/", depth=2, limit=50)
    dataset = hydrate_dataset(raw_dict)
    stats = dataset.crawl_stats

    # Previous Functionality Validation
    assert stats.urls_discovered > 0
    assert stats.robots_blocked >= 1
    assert stats.redirects >= 1
    assert stats.failed_pages >= 1
    assert stats.non_html_responses >= 1
    
    # 2. Phase 4: Register rule and run engine
    registry = RuleRegistry()
    registry.register(E2EDummyRule())
    
    result = RuleEngine.run(dataset, registry)
    
    # Validation of Phase 4 outputs
    assert result.total_rules_run == 1
    assert result.successful_rules == 1
    assert result.failed_rules == 0
    
    diag = result.diagnostics[0]
    assert diag.rule_id == "E2E-TEST-RULE"
    assert diag.status == RuleExecutionStatus.SUCCESS
    assert diag.findings_generated == 1
    assert diag.valid_findings == 1
    assert diag.invalid_findings == 0
    
    # Phase 3 serialization validation
    finding = result.findings[0]
    assert finding.trigger.rule_id == "E2E-TEST-RULE"
    assert finding.evidence.page.endswith("/about")
    
    finding_dict = finding.to_dict()
    json_str = json.dumps(finding_dict)
    reloaded = json.loads(json_str)
    assert reloaded["pipeline"] == "ai_discoverability"
    
    print("\nPhase 1 -> Phase 2 -> Phase 3 -> Phase 4 E2E Stats:")
    print(f"urls_discovered: {stats.urls_discovered}")
    print(f"urls_scheduled: {stats.urls_scheduled}")
    print(f"requests_attempted: {stats.requests_attempted}")
    print(f"responses_received: {stats.responses_received}")
    print(f"html_pages_crawled: {stats.html_pages_crawled}")
    print(f"successful_pages: {stats.successful_pages}")
    print(f"failed_pages: {stats.failed_pages}")
    print(f"robots_blocked: {stats.robots_blocked}")
    print(f"duplicate_urls: {stats.duplicate_urls}")
    print(f"redirects: {stats.redirects}")
    print(f"non_html_responses: {stats.non_html_responses}")
    print("\nEngine Execution:")
    print(f"Rules run: {result.total_rules_run}")
    print(f"Successful rules: {result.successful_rules}")
    print(f"Valid findings output: {len(result.findings)}\n")
