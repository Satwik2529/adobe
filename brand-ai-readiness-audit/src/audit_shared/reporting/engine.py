from typing import List
from datetime import datetime
from audit_shared.models.data_flow import CrawlDataset
from audit_shared.models.finding import Finding, Severity
from audit_shared.validation.evidence_validator import ValidationResult
from audit_shared.reporting.models import FinalReport, CrawlSummary, SeveritySummary, DiagnosticSummary
from audit_shared.reporting.scoring import calculate_score

class ReportingEngine:
    @classmethod
    def generate_report(cls, dataset: CrawlDataset, validation_result: ValidationResult) -> FinalReport:
        # Extract valid canonical findings
        valid_findings: List[Finding] = [group.canonical_finding for group in validation_result.valid_groups]
        
        # Sort deterministicly by pipeline -> severity -> title
        valid_findings.sort(key=lambda f: (
            f.pipeline.value,
            cls._severity_sort_key(f.severity),
            f.title
        ))
        
        # Determine crawl status
        pages_evaluated = len(dataset.pages)
        if len(dataset.unfetched_urls) > 0:
            if dataset.raw_scrapy_stats.get("finish_reason") == "closespider_pagecount":
                status = "Partial (Configured page limit reached)"
            else:
                status = "Partial (Did not evaluate all discovered URLs)"
        else:
            status = "Complete"
            
        crawl_summary = CrawlSummary(
            status=status,
            pages_evaluated=pages_evaluated
        )
        
        # Calculate Severities
        high = sum(1 for f in valid_findings if f.severity == Severity.HIGH)
        medium = sum(1 for f in valid_findings if f.severity == Severity.MEDIUM)
        low = sum(1 for f in valid_findings if f.severity == Severity.LOW)
        info = sum(1 for f in valid_findings if f.severity == Severity.INFO)
        total = len(valid_findings)
        
        score = calculate_score(valid_findings)
        
        severity_summary = SeveritySummary(
            score=score,
            total_findings=total,
            high=high,
            medium=medium,
            low=low,
            info=info
        )
        
        # Diagnostics
        diag = DiagnosticSummary(
            findings_evaluated=validation_result.total_checked,
            evidence_valid_findings=len(validation_result.valid_groups),
            excluded_during_validation=len(validation_result.invalid_groups)
        )
        
        return FinalReport(
            site=dataset.seed_url,
            audited_at=datetime.utcnow().isoformat() + "Z",
            crawl=crawl_summary,
            summary=severity_summary,
            diagnostics=diag,
            findings=valid_findings
        )
        
    @staticmethod
    def _severity_sort_key(sev: Severity) -> int:
        mapping = {
            Severity.CRITICAL: 0,
            Severity.HIGH: 1,
            Severity.MEDIUM: 2,
            Severity.LOW: 3,
            Severity.INFO: 4
        }
        return mapping.get(sev, 99)
