from typing import List, Dict, Optional, Tuple
import datetime

from audit_shared.models.finding import (
    Finding, Pipeline, Severity, Trigger, TriggerType, SuggestedAction, ActionPriority, Evidence, generate_finding_id
)
from audit_shared.models.data_flow import CrawlDataset, PageRecord
from audit_shared.rules.base import AuditRule
from audit_shared.utils.date_parser import (
    parse_date_with_status, parse_date, is_future_date, 
    are_dates_equivalent, are_same_utc_calendar_day, is_valid_chronology
)

ARTICLE_STALE_YEARS = 2
PRODUCT_STALE_YEARS = 3

class FreshnessRuleBase(AuditRule):
    @property
    def pipeline(self) -> Pipeline:
        return Pipeline.FRESHNESS

def get_canonical_audit_time(dataset: CrawlDataset) -> datetime.datetime:
    dt = parse_date(dataset.crawled_at)
    if not dt:
        # Fallback just in case, though crawled_at should be ISO string
        dt = datetime.datetime.now(datetime.timezone.utc)
    return dt

def _get_parsed_dates(page: PageRecord) -> List[Dict]:
    # We can cache this on the page object dynamically to avoid re-parsing
    if not hasattr(page, '_parsed_dates_cache'):
        parsed = []
        for dc in page.extracted.date_candidates:
            dt, status = parse_date_with_status(dc.value)
            parsed.append({
                'candidate': dc,
                'dt': dt,
                'status': status
            })
        page._parsed_dates_cache = parsed
    return page._parsed_dates_cache

class MissingExpectedDateRule(FreshnessRuleBase):
    @property
    def rule_id(self) -> str: return "FR-DATE-001"
    @property
    def description(self) -> str: return "Missing Expected Date Signal"

    def evaluate(self, dataset: CrawlDataset) -> List[Finding]:
        findings = []
        for page in dataset.pages:
            if page.status_code == 200 and page.content_type.startswith('text/html'):
                if page.extracted.page_type in ('article', 'news'):
                    parsed = _get_parsed_dates(page)
                    valid_dates = [p for p in parsed if p['status'] == 'VALID']
                    if not valid_dates:
                        findings.append(Finding(
                            id=generate_finding_id(self.rule_id, [page.url]),
                            pipeline=self.pipeline,
                            title="Missing Expected Date Signal",
                            severity=Severity.MEDIUM,
                            trigger=Trigger(rule_id=self.rule_id, type=TriggerType.DETERMINISTIC),
                            suggested_action=SuggestedAction(summary="Add datePublished or article:published_time.", priority=ActionPriority.MEDIUM),
                            evidence=Evidence(
                                page=page.url, source="extracted", field="date_candidates",
                                observed_value="No valid date found", pages_checked=1, pages_affected=1, affected_percentage=100.0
                            )
                        ))
        return findings

class UnparseableDateRule(FreshnessRuleBase):
    @property
    def rule_id(self) -> str: return "FR-DATE-002"
    @property
    def description(self) -> str: return "Unparseable Date Value"

    def evaluate(self, dataset: CrawlDataset) -> List[Finding]:
        findings = []
        for page in dataset.pages:
            if page.status_code == 200 and page.content_type.startswith('text/html'):
                parsed = _get_parsed_dates(page)
                for p in parsed:
                    if p['status'] == 'UNPARSEABLE':
                        findings.append(Finding(
                            id=generate_finding_id(self.rule_id, [page.url, p['candidate'].source, p['candidate'].field]),
                            pipeline=self.pipeline,
                            title="Unparseable Date Value",
                            severity=Severity.LOW,
                            trigger=Trigger(rule_id=self.rule_id, type=TriggerType.DETERMINISTIC),
                            suggested_action=SuggestedAction(summary="Fix date format to use standard ISO 8601.", priority=ActionPriority.LOW),
                            evidence=Evidence(
                                page=page.url, source=p['candidate'].source, field=p['candidate'].field,
                                observed_value=f"Unparseable format: '{p['candidate'].value}'", pages_checked=1, pages_affected=1, affected_percentage=100.0
                            )
                        ))
        return findings

class CalendarImpossibleDateRule(FreshnessRuleBase):
    @property
    def rule_id(self) -> str: return "FR-DATE-003"
    @property
    def description(self) -> str: return "Calendar-Impossible Date"

    def evaluate(self, dataset: CrawlDataset) -> List[Finding]:
        findings = []
        for page in dataset.pages:
            if page.status_code == 200 and page.content_type.startswith('text/html'):
                parsed = _get_parsed_dates(page)
                for p in parsed:
                    if p['status'] == 'IMPOSSIBLE':
                        findings.append(Finding(
                            id=generate_finding_id(self.rule_id, [page.url, p['candidate'].source, p['candidate'].field]),
                            pipeline=self.pipeline,
                            title="Calendar-Impossible Date",
                            severity=Severity.HIGH,
                            trigger=Trigger(rule_id=self.rule_id, type=TriggerType.DETERMINISTIC),
                            suggested_action=SuggestedAction(summary="Fix impossible calendar date (e.g. Feb 30).", priority=ActionPriority.HIGH),
                            evidence=Evidence(
                                page=page.url, source=p['candidate'].source, field=p['candidate'].field,
                                observed_value=f"Impossible date: '{p['candidate'].value}'", pages_checked=1, pages_affected=1, affected_percentage=100.0
                            )
                        ))
        return findings

class FutureDateRule(FreshnessRuleBase):
    @property
    def rule_id(self) -> str: return "FR-DATE-004"
    @property
    def description(self) -> str: return "Future Date Value"

    def evaluate(self, dataset: CrawlDataset) -> List[Finding]:
        audit_time = get_canonical_audit_time(dataset)
        findings = []
        for page in dataset.pages:
            if page.status_code == 200 and page.content_type.startswith('text/html'):
                parsed = _get_parsed_dates(page)
                for p in parsed:
                    if p['status'] == 'VALID' and p['dt']:
                        if is_future_date(p['dt'], audit_time):
                            findings.append(Finding(
                                id=generate_finding_id(self.rule_id, [page.url, p['candidate'].source, p['candidate'].field]),
                                pipeline=self.pipeline,
                                title="Future Date Value",
                                severity=Severity.HIGH,
                                trigger=Trigger(rule_id=self.rule_id, type=TriggerType.DETERMINISTIC),
                                suggested_action=SuggestedAction(summary="Correct date to not be in the future.", priority=ActionPriority.HIGH),
                                evidence=Evidence(
                                    page=page.url, source=p['candidate'].source, field=p['candidate'].field,
                                    observed_value=f"Future date: '{p['candidate'].value}' (Normalized: {p['dt'].isoformat()}) vs Audit Time: {audit_time.isoformat()}", 
                                    pages_checked=1, pages_affected=1, affected_percentage=100.0
                                )
                            ))
        return findings

class ContradictoryChronologyRule(FreshnessRuleBase):
    @property
    def rule_id(self) -> str: return "FR-CONS-001"
    @property
    def description(self) -> str: return "Contradictory Chronology"

    def evaluate(self, dataset: CrawlDataset) -> List[Finding]:
        findings = []
        for page in dataset.pages:
            if page.status_code == 200 and page.content_type.startswith('text/html'):
                parsed = _get_parsed_dates(page)
                # Find best published and modified dates
                published_dts = [p['dt'] for p in parsed if p['status'] == 'VALID' and 'publish' in p['candidate'].field.lower()]
                modified_dts = [p['dt'] for p in parsed if p['status'] == 'VALID' and 'modif' in p['candidate'].field.lower()]
                
                if published_dts and modified_dts:
                    pub = published_dts[0]
                    mod = modified_dts[0]
                    if not is_valid_chronology(pub, mod, tolerance_hours=24):
                        findings.append(Finding(
                            id=generate_finding_id(self.rule_id, [page.url]),
                            pipeline=self.pipeline,
                            title="Contradictory Chronology",
                            severity=Severity.MEDIUM,
                            trigger=Trigger(rule_id=self.rule_id, type=TriggerType.DETERMINISTIC),
                            suggested_action=SuggestedAction(summary="Ensure datePublished is before dateModified.", priority=ActionPriority.MEDIUM),
                            evidence=Evidence(
                                page=page.url, source="extracted", field="dates",
                                observed_value=f"Published {pub.isoformat()} occurs > 24h after Modified {mod.isoformat()}", 
                                pages_checked=1, pages_affected=1, affected_percentage=100.0
                            )
                        ))
        return findings

class DateSourceContradictionRule(FreshnessRuleBase):
    @property
    def rule_id(self) -> str: return "FR-CONS-002"
    @property
    def description(self) -> str: return "Date Source Contradiction"

    def evaluate(self, dataset: CrawlDataset) -> List[Finding]:
        findings = []
        for page in dataset.pages:
            if page.status_code == 200 and page.content_type.startswith('text/html'):
                parsed = _get_parsed_dates(page)
                meta_pubs = [p for p in parsed if p['status'] == 'VALID' and p['candidate'].source == 'meta' and 'publish' in p['candidate'].field.lower()]
                jsonld_pubs = [p for p in parsed if p['status'] == 'VALID' and p['candidate'].source == 'json_ld' and 'publish' in p['candidate'].field.lower()]
                
                if meta_pubs and jsonld_pubs:
                    m_dt = meta_pubs[0]['dt']
                    j_dt = jsonld_pubs[0]['dt']
                    
                    if not are_dates_equivalent(m_dt, j_dt) and not are_same_utc_calendar_day(m_dt, j_dt):
                        findings.append(Finding(
                            id=generate_finding_id(self.rule_id, [page.url]),
                            pipeline=self.pipeline,
                            title="Date Source Contradiction",
                            severity=Severity.MEDIUM,
                            trigger=Trigger(rule_id=self.rule_id, type=TriggerType.DETERMINISTIC),
                            suggested_action=SuggestedAction(summary="Ensure meta and json-ld dates are equivalent.", priority=ActionPriority.MEDIUM),
                            evidence=Evidence(
                                page=page.url, source="extracted", field="dates",
                                observed_value=f"Meta ({m_dt.isoformat()}) and JSON-LD ({j_dt.isoformat()}) differ significantly", 
                                pages_checked=1, pages_affected=1, affected_percentage=100.0
                            )
                        ))
        return findings

def _get_best_date(parsed: List[Dict]) -> Optional[datetime.datetime]:
    valid = [p['dt'] for p in parsed if p['status'] == 'VALID']
    if not valid:
        return None
    return max(valid)

class StaleTimeSensitiveRule(FreshnessRuleBase):
    @property
    def rule_id(self) -> str: return "FR-STALE-001"
    @property
    def description(self) -> str: return "Stale Time-Sensitive Content"

    def evaluate(self, dataset: CrawlDataset) -> List[Finding]:
        audit_time = get_canonical_audit_time(dataset)
        findings = []
        for page in dataset.pages:
            if page.status_code == 200 and page.content_type.startswith('text/html'):
                if page.extracted.page_type in ('article', 'news'):
                    parsed = _get_parsed_dates(page)
                    best_dt = _get_best_date(parsed)
                    if best_dt:
                        age_days = (audit_time - best_dt).days
                        if age_days > ARTICLE_STALE_YEARS * 365:
                            findings.append(Finding(
                                id=generate_finding_id(self.rule_id, [page.url]),
                                pipeline=self.pipeline,
                                title="Stale Time-Sensitive Content",
                                severity=Severity.MEDIUM,
                                trigger=Trigger(rule_id=self.rule_id, type=TriggerType.DETERMINISTIC),
                                suggested_action=SuggestedAction(summary="Review or update stale article.", priority=ActionPriority.MEDIUM),
                                evidence=Evidence(
                                    page=page.url, source="extracted", field="dates",
                                    observed_value=f"Age > {ARTICLE_STALE_YEARS} years: ({best_dt.isoformat()})", 
                                    pages_checked=1, pages_affected=1, affected_percentage=100.0
                                )
                            ))
        return findings

class StaleProductRule(FreshnessRuleBase):
    @property
    def rule_id(self) -> str: return "FR-STALE-002"
    @property
    def description(self) -> str: return "Stale Product Content"

    def evaluate(self, dataset: CrawlDataset) -> List[Finding]:
        audit_time = get_canonical_audit_time(dataset)
        findings = []
        for page in dataset.pages:
            if page.status_code == 200 and page.content_type.startswith('text/html'):
                if page.extracted.page_type in ('product', 'pricing'):
                    parsed = _get_parsed_dates(page)
                    best_dt = _get_best_date(parsed)
                    if best_dt:
                        age_days = (audit_time - best_dt).days
                        if age_days > PRODUCT_STALE_YEARS * 365:
                            findings.append(Finding(
                                id=generate_finding_id(self.rule_id, [page.url]),
                                pipeline=self.pipeline,
                                title="Stale Product Content",
                                severity=Severity.LOW,
                                trigger=Trigger(rule_id=self.rule_id, type=TriggerType.DETERMINISTIC),
                                suggested_action=SuggestedAction(summary="Review or update stale product page.", priority=ActionPriority.LOW),
                                evidence=Evidence(
                                    page=page.url, source="extracted", field="dates",
                                    observed_value=f"Age > {PRODUCT_STALE_YEARS} years: ({best_dt.isoformat()})", 
                                    pages_checked=1, pages_affected=1, affected_percentage=100.0
                                )
                            ))
        return findings

def register_freshness_rules(registry):
    registry.register(MissingExpectedDateRule())
    registry.register(UnparseableDateRule())
    registry.register(CalendarImpossibleDateRule())
    registry.register(FutureDateRule())
    registry.register(ContradictoryChronologyRule())
    registry.register(DateSourceContradictionRule())
    registry.register(StaleTimeSensitiveRule())
    registry.register(StaleProductRule())
