from typing import List
from datetime import datetime, timezone
from audit_shared.models.data_flow import CrawlDataset
from audit_shared.models.finding import Finding, Severity
from audit_shared.validation.evidence_validator import ValidationResult
from audit_shared.reporting.models import FinalReport, CrawlMetrics, EvaluationScope, SeveritySummary, DiagnosticSummary
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
        
        crawl_metrics = CrawlMetrics(
            urls_discovered=dataset.crawl_stats.urls_discovered,
            urls_scheduled=dataset.crawl_stats.urls_scheduled,
            requests_attempted=dataset.crawl_stats.requests_attempted,
            responses_received=dataset.crawl_stats.responses_received,
            html_pages_crawled=dataset.crawl_stats.html_pages_crawled,
            successful_pages=dataset.crawl_stats.successful_pages,
            failed_pages=dataset.crawl_stats.failed_pages,
            robots_blocked=dataset.crawl_stats.robots_blocked,
            duplicate_urls=dataset.crawl_stats.duplicate_urls,
            redirects=dataset.crawl_stats.redirects,
            non_html_responses=dataset.crawl_stats.non_html_responses,
            crawl_duration_seconds=dataset.crawl_stats.crawl_duration
        )
        
        # Evaluation scope
        pages_evaluated = len(dataset.pages)
        if len(dataset.unfetched_urls) > 0:
            if dataset.raw_scrapy_stats.get("finish_reason") == "closespider_pagecount":
                status = "Partial"
                reason = "Configured page limit reached"
            else:
                status = "Partial"
                reason = "Did not evaluate all discovered URLs"
        else:
            status = "Complete"
            reason = "Evaluated all discovered URLs"
            
        eval_scope = EvaluationScope(
            status=status,
            reason=reason,
            pages_evaluated=pages_evaluated,
            max_pages=dataset.crawl_diagnostics.configured_page_limit,
            max_depth=dataset.crawl_diagnostics.configured_depth_limit,
            robots_respected=True, # Assuming always true for now, can be extracted if we add flag
            termination_reason=dataset.crawl_diagnostics.crawl_termination_reason
        )
        
        # Diagnostics
        diag = DiagnosticSummary(
            findings_evaluated=validation_result.total_checked,
            evidence_valid_findings=len(validation_result.valid_groups),
            excluded_findings=len(validation_result.invalid_groups)
        )
        
        return FinalReport(
            site=dataset.seed_url,
            audited_at=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            summary=severity_summary,
            crawl=crawl_metrics,
            evaluation_scope=eval_scope,
            findings=valid_findings,
            diagnostics=diag
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
