from dataclasses import dataclass
from typing import List, Dict, Any
from audit_shared.models.finding import Finding

@dataclass
class CrawlSummary:
    status: str
    pages_evaluated: int

@dataclass
class SeveritySummary:
    score: int
    total_findings: int
    high: int
    medium: int
    low: int
    info: int

@dataclass
class DiagnosticSummary:
    findings_evaluated: int
    evidence_valid_findings: int
    excluded_during_validation: int

@dataclass
class FinalReport:
    site: str
    audited_at: str
    crawl: CrawlSummary
    summary: SeveritySummary
    diagnostics: DiagnosticSummary
    findings: List[Finding]

    def to_dict(self) -> Dict[str, Any]:
        """Custom serialization to preserve clean JSON."""
        return {
            "site": self.site,
            "audited_at": self.audited_at,
            "crawl": {
                "status": self.crawl.status,
                "pages_evaluated": self.crawl.pages_evaluated,
            },
            "summary": {
                "score": self.summary.score,
                "total_findings": self.summary.total_findings,
                "high": self.summary.high,
                "medium": self.summary.medium,
                "low": self.summary.low,
                "info": self.summary.info,
            },
            "diagnostics": {
                "findings_evaluated": self.diagnostics.findings_evaluated,
                "evidence_valid_findings": self.diagnostics.evidence_valid_findings,
                "excluded_during_validation": self.diagnostics.excluded_during_validation,
            },
            "findings": [f.to_dict() for f in self.findings]
        }
