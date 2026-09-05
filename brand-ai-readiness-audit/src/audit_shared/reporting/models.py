from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from audit_shared.models.finding import Finding
from audit_shared.genai.diagnostics import GenAIDiagnostics, StageTiming

@dataclass
class SeveritySummary:
    score: int
    total_findings: int
    high: int
    medium: int
    low: int
    info: int

@dataclass
class CrawlMetrics:
    urls_discovered: int
    urls_scheduled: int
    requests_attempted: int
    responses_received: int
    html_pages_crawled: int
    successful_pages: int
    failed_pages: int
    robots_blocked: int
    duplicate_urls: int
    redirects: int
    non_html_responses: int
    crawl_duration_seconds: float

@dataclass
class EvaluationScope:
    status: str
    reason: str
    pages_evaluated: int
    max_pages: int
    max_depth: int
    robots_respected: bool
    termination_reason: str

@dataclass
class NLPMetrics:
    candidates: int
    eligible: int
    analyzed: int
    successful: int
    no_observation: int
    semantic_findings: int
    skipped: int
    failures: int

@dataclass
class DiagnosticSummary:
    findings_evaluated: int
    evidence_valid_findings: int
    excluded_findings: int
    nlp: Optional[NLPMetrics] = None
    genai: Optional[GenAIDiagnostics] = None
    stage_timing: Optional[StageTiming] = None

@dataclass
class FinalReport:
    site: str
    audited_at: str
    summary: SeveritySummary
    crawl: CrawlMetrics
    evaluation_scope: EvaluationScope
    findings: List[Finding]
    diagnostics: DiagnosticSummary

    def to_dict(self) -> Dict[str, Any]:
        """Custom serialization to preserve clean JSON exactly matching the contract."""
        data = {
            "site": self.site,
            "audited_at": self.audited_at,
            "summary": {
                "overall_score": self.summary.score,
                "total_findings": self.summary.total_findings,
                "severity": {
                    "high": self.summary.high,
                    "medium": self.summary.medium,
                    "low": self.summary.low,
                    "info": self.summary.info,
                }
            },
            "crawl": {
                "urls_discovered": self.crawl.urls_discovered,
                "urls_scheduled": self.crawl.urls_scheduled,
                "requests_attempted": self.crawl.requests_attempted,
                "responses_received": self.crawl.responses_received,
                "html_pages_crawled": self.crawl.html_pages_crawled,
                "successful_pages": self.crawl.successful_pages,
                "failed_pages": self.crawl.failed_pages,
                "robots_blocked": self.crawl.robots_blocked,
                "duplicate_urls": self.crawl.duplicate_urls,
                "redirects": self.crawl.redirects,
                "non_html_responses": self.crawl.non_html_responses,
                "crawl_duration_seconds": self.crawl.crawl_duration_seconds,
            },
            "evaluation_scope": {
                "status": self.evaluation_scope.status,
                "reason": self.evaluation_scope.reason,
                "pages_evaluated": self.evaluation_scope.pages_evaluated,
                "max_pages": self.evaluation_scope.max_pages,
                "max_depth": self.evaluation_scope.max_depth,
                "robots_respected": self.evaluation_scope.robots_respected,
                "termination_reason": self.evaluation_scope.termination_reason,
            },
            "findings": [f.to_dict() for f in self.findings],
            "diagnostics": {
                "findings_evaluated": self.diagnostics.findings_evaluated,
                "evidence_valid_findings": self.diagnostics.evidence_valid_findings,
                "excluded_findings": self.diagnostics.excluded_findings,
            }
        }
        
        if self.diagnostics.nlp:
            from dataclasses import asdict
            data["diagnostics"]["nlp"] = asdict(self.diagnostics.nlp)
            
        if self.diagnostics.genai:
            from dataclasses import asdict
            data["diagnostics"]["genai"] = asdict(self.diagnostics.genai)
            
        if self.diagnostics.stage_timing:
            from dataclasses import asdict
            data["diagnostics"]["stage_timing"] = asdict(self.diagnostics.stage_timing)
            
        return data
