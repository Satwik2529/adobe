from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from audit_shared.models.finding import Finding
from audit_shared.genai.diagnostics import GenAIDiagnostics, StageTiming

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
    genai_diagnostics: Optional[GenAIDiagnostics] = None
    stage_timing: Optional[StageTiming] = None

    def to_dict(self) -> Dict[str, Any]:
        """Custom serialization to preserve clean JSON."""
        data = {
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
        
        if self.genai_diagnostics:
            from dataclasses import asdict
            data["genai_diagnostics"] = asdict(self.genai_diagnostics)
            
        if self.stage_timing:
            from dataclasses import asdict
            data["stage_timing"] = asdict(self.stage_timing)
            
        return data
