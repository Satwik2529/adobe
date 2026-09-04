import pytest
import datetime
from typing import List
from audit_shared.utils.date_parser import (
    parse_date, parse_date_with_status, is_future_date, 
    are_dates_equivalent, are_same_utc_calendar_day, is_valid_chronology
)
from audit_shared.models.data_flow import CrawlDataset, PageRecord, ExtractedData, ExtractionDiagnostics, DateCandidate
from audit_shared.rules.freshness import (
    MissingExpectedDateRule, UnparseableDateRule, CalendarImpossibleDateRule,
    FutureDateRule, ContradictoryChronologyRule, DateSourceContradictionRule,
    StaleTimeSensitiveRule, StaleProductRule
)
from audit_shared.validation.finding_validator import FindingValidator

# --- DATE PARSER TESTS ---

def test_parse_date_iso():
    dt = parse_date("2024-01-01")
    assert dt is not None
    assert dt.year == 2024
    assert dt.month == 1
    assert dt.day == 1
    assert dt.tzinfo == datetime.timezone.utc

def test_parse_date_iso_datetime():
    dt = parse_date("2024-01-01T12:00:00Z")
    assert dt is not None
    assert dt.hour == 12
    assert dt.tzinfo == datetime.timezone.utc

def test_parse_date_timezone_aware():
    dt = parse_date("2024-01-01T05:00:00-05:00")
    assert dt is not None
    assert dt.tzinfo == datetime.timezone.utc
    # 05:00 -0500 is 10:00 UTC
    assert dt.hour == 10

def test_parse_date_timezone_naive():
    dt = parse_date("2024-01-01T12:00:00")
    assert dt is not None
    assert dt.tzinfo == datetime.timezone.utc
    assert dt.hour == 12

def test_parse_date_invalid():
    dt, status = parse_date_with_status("yesterday")
    assert dt is None
    assert status == "UNPARSEABLE"

def test_parse_date_calendar_impossible():
    dt, status = parse_date_with_status("2024-02-30")
    assert dt is None
    assert status == "IMPOSSIBLE"

def test_is_future_date():
    audit_time = datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc)
    future_dt = datetime.datetime(2024, 1, 3, tzinfo=datetime.timezone.utc)
    past_dt = datetime.datetime(2023, 1, 1, tzinfo=datetime.timezone.utc)
    assert is_future_date(future_dt, audit_time)
    assert not is_future_date(past_dt, audit_time)
    
    # Within 24h tolerance
    close_future_dt = datetime.datetime(2024, 1, 1, 12, tzinfo=datetime.timezone.utc)
    assert not is_future_date(close_future_dt, audit_time)

def test_are_dates_equivalent():
    dt1 = parse_date("2024-01-01T05:00:00-05:00")
    dt2 = parse_date("2024-01-01T10:00:00Z")
    assert are_dates_equivalent(dt1, dt2)

def test_are_same_utc_calendar_day():
    dt1 = parse_date("2024-01-01")
    dt2 = parse_date("2024-01-01T23:59:59Z")
    assert are_same_utc_calendar_day(dt1, dt2)

def test_is_valid_chronology():
    published = parse_date("2024-01-01T10:00:00Z")
    modified = parse_date("2024-01-02T10:00:00Z")
    assert is_valid_chronology(published, modified)

    # published slightly after modified (within 24h)
    published_late = parse_date("2024-01-02T12:00:00Z")
    assert is_valid_chronology(published_late, modified)

    # published way after modified (invalid)
    published_very_late = parse_date("2024-02-01T10:00:00Z")
    assert not is_valid_chronology(published_very_late, modified)

# --- RULE TESTS ---

def mock_dataset(pages: List[PageRecord], crawled_at: str = "2024-09-04T00:00:00Z") -> CrawlDataset:
    return CrawlDataset(
        seed_url="https://example.com",
        crawled_at=crawled_at,
        pages=pages
    )

def mock_page(url: str, page_type: str = "unknown", date_candidates: List[DateCandidate] = None) -> PageRecord:
    ext = ExtractedData(
        page_type=page_type,
        date_candidates=date_candidates or []
    )
    return PageRecord(
        url=url,
        final_url=url,
        parent_url=None,
        status_code=200,
        content_type="text/html",
        depth=1,
        extracted=ext,
        diagnostics=ExtractionDiagnostics(),
        redirect_chain=[]
    )

def assert_valid_finding(finding, dataset):
    validator = FindingValidator()
    errors = validator.validate(finding, dataset)
    assert not errors, f"Validation failed: {errors}"

def test_missing_expected_date_rule():
    rule = MissingExpectedDateRule()
    # Positive: article missing date
    p1 = mock_page("https://example.com/1", page_type="article")
    # Negative: article with date
    p2 = mock_page("https://example.com/2", page_type="article", date_candidates=[DateCandidate("2024-01-01", "meta", "article:published_time")])
    # Boundary/Must-not-trigger: unknown page missing date
    p3 = mock_page("https://example.com/3", page_type="unknown")

    ds = mock_dataset([p1, p2, p3])
    findings = rule.evaluate(ds)
    assert len(findings) == 1
    assert findings[0].evidence.page == "https://example.com/1"
    assert_valid_finding(findings[0], ds)

def test_unparseable_date_rule():
    rule = UnparseableDateRule()
    p1 = mock_page("https://example.com/1", date_candidates=[DateCandidate("yesterday", "meta", "article:published_time")])
    p2 = mock_page("https://example.com/2", date_candidates=[DateCandidate("2024-01-01", "meta", "article:published_time")])
    ds = mock_dataset([p1, p2])
    findings = rule.evaluate(ds)
    assert len(findings) == 1
    assert "Unparseable" in findings[0].evidence.observed_value
    assert_valid_finding(findings[0], ds)

def test_calendar_impossible_date_rule():
    rule = CalendarImpossibleDateRule()
    p1 = mock_page("https://example.com/1", date_candidates=[DateCandidate("2024-02-30", "meta", "article:published_time")])
    ds = mock_dataset([p1])
    findings = rule.evaluate(ds)
    assert len(findings) == 1
    assert "Impossible date" in findings[0].evidence.observed_value
    assert_valid_finding(findings[0], ds)

def test_future_date_rule():
    rule = FutureDateRule()
    # Canonical time is 2024-09-04
    p1 = mock_page("https://example.com/1", date_candidates=[DateCandidate("2099-01-01", "meta", "article:published_time")])
    p2 = mock_page("https://example.com/2", date_candidates=[DateCandidate("2024-01-01", "meta", "article:published_time")])
    ds = mock_dataset([p1, p2])
    findings = rule.evaluate(ds)
    assert len(findings) == 1
    assert "Future date" in findings[0].evidence.observed_value
    assert_valid_finding(findings[0], ds)

def test_contradictory_chronology_rule():
    rule = ContradictoryChronologyRule()
    # Published way after modified
    p1 = mock_page("https://example.com/1", date_candidates=[
        DateCandidate("2024-03-01", "meta", "article:published_time"),
        DateCandidate("2024-01-01", "meta", "article:modified_time")
    ])
    # Normal (pub before mod)
    p2 = mock_page("https://example.com/2", date_candidates=[
        DateCandidate("2024-01-01", "meta", "article:published_time"),
        DateCandidate("2024-03-01", "meta", "article:modified_time")
    ])
    ds = mock_dataset([p1, p2])
    findings = rule.evaluate(ds)
    assert len(findings) == 1
    assert "after Modified" in findings[0].evidence.observed_value
    assert_valid_finding(findings[0], ds)

def test_date_source_contradiction_rule():
    rule = DateSourceContradictionRule()
    # Genuinely different (contradiction)
    p1 = mock_page("https://example.com/1", date_candidates=[
        DateCandidate("2024-01-01", "meta", "article:published_time"),
        DateCandidate("2024-03-01", "json_ld", "datePublished")
    ])
    # Equivalent (timezone equivalent) - No contradiction
    p2 = mock_page("https://example.com/2", date_candidates=[
        DateCandidate("2024-01-01T05:00:00-05:00", "meta", "article:published_time"),
        DateCandidate("2024-01-01T10:00:00Z", "json_ld", "datePublished")
    ])
    # Exact timestamps match - No contradiction
    p3 = mock_page("https://example.com/3", date_candidates=[
        DateCandidate("2024-05-05T12:00:00Z", "meta", "article:published_time"),
        DateCandidate("2024-05-05T12:00:00Z", "json_ld", "datePublished")
    ])
    # Date-only vs Date-only same calendar date - No contradiction
    p4 = mock_page("https://example.com/4", date_candidates=[
        DateCandidate("2024-06-01", "meta", "article:published_time"),
        DateCandidate("2024-06-01", "json_ld", "datePublished")
    ])
    # Date-only vs Datetime on same UTC calendar day - No contradiction
    p5 = mock_page("https://example.com/5", date_candidates=[
        DateCandidate("2024-07-01", "meta", "article:published_time"),
        DateCandidate("2024-07-01T23:59:59Z", "json_ld", "datePublished")
    ])
    # Genuinely different but within 24h (e.g. 1 hour difference but not same calendar day) -> Contradiction!
    # Or just different times on same day? Wait, same calendar day means no contradiction.
    # What if they are on DIFFERENT calendar days but within 24h?
    # e.g. 2024-08-01T23:00:00Z and 2024-08-02T01:00:00Z (2 hours apart, different days) -> Contradiction!
    p6 = mock_page("https://example.com/6", date_candidates=[
        DateCandidate("2024-08-01T23:00:00Z", "meta", "article:published_time"),
        DateCandidate("2024-08-02T01:00:00Z", "json_ld", "datePublished")
    ])
    
    ds = mock_dataset([p1, p2, p3, p4, p5, p6])
    findings = rule.evaluate(ds)
    
    assert len(findings) == 2
    urls = [f.evidence.page for f in findings]
    assert "https://example.com/1" in urls
    assert "https://example.com/6" in urls
    assert_valid_finding(findings[0], ds)

def test_stale_time_sensitive_rule():
    rule = StaleTimeSensitiveRule()
    # audit is 2024-09-04
    # Stale article (>2 years) - e.g. 2020-01-01
    p_stale = mock_page("https://example.com/stale", page_type="article", date_candidates=[DateCandidate("2020-01-01", "meta", "article:published_time")])
    
    import datetime
    audit_time = datetime.datetime(2024, 9, 4, tzinfo=datetime.timezone.utc)
    exact_threshold_dt = audit_time - datetime.timedelta(days=2 * 365)
    
    # Just under threshold (1 day before threshold)
    just_under_dt = exact_threshold_dt + datetime.timedelta(days=1)
    p_just_under = mock_page("https://example.com/just_under", page_type="article", date_candidates=[DateCandidate(just_under_dt.strftime("%Y-%m-%d"), "meta", "article:published_time")])
    
    # Exactly at threshold (exactly 2*365 days ago) -> No finding (must be >)
    p_exact = mock_page("https://example.com/exact", page_type="article", date_candidates=[DateCandidate(exact_threshold_dt.strftime("%Y-%m-%d"), "meta", "article:published_time")])
    
    # Just over threshold (1 day over threshold) -> Finding
    just_over_dt = exact_threshold_dt - datetime.timedelta(days=1)
    p_just_over = mock_page("https://example.com/just_over", page_type="article", date_candidates=[DateCandidate(just_over_dt.strftime("%Y-%m-%d"), "meta", "article:published_time")])
    
    # Fresh article
    p_fresh = mock_page("https://example.com/fresh", page_type="article", date_candidates=[DateCandidate("2024-01-01", "meta", "article:published_time")])
    
    # Stale unknown (must not trigger)
    p_unknown = mock_page("https://example.com/unknown", page_type="unknown", date_candidates=[DateCandidate("2015-01-01", "meta", "article:published_time")])
    
    ds = mock_dataset([p_stale, p_just_under, p_exact, p_just_over, p_fresh, p_unknown])
    findings = rule.evaluate(ds)
    
    assert len(findings) == 2
    urls = [f.evidence.page for f in findings]
    assert "https://example.com/stale" in urls
    assert "https://example.com/just_over" in urls
    assert_valid_finding(findings[0], ds)

def test_stale_product_rule():
    rule = StaleProductRule()
    # audit is 2024-09-04
    # Stale product (>3 years) - 2019-01-01
    p_stale = mock_page("https://example.com/stale", page_type="product", date_candidates=[DateCandidate("2019-01-01", "json_ld", "datePublished")])
    
    import datetime
    audit_time = datetime.datetime(2024, 9, 4, tzinfo=datetime.timezone.utc)
    exact_threshold_dt = audit_time - datetime.timedelta(days=3 * 365)
    
    # Just under threshold (1 day before threshold)
    just_under_dt = exact_threshold_dt + datetime.timedelta(days=1)
    p_just_under = mock_page("https://example.com/just_under", page_type="product", date_candidates=[DateCandidate(just_under_dt.strftime("%Y-%m-%d"), "json_ld", "datePublished")])
    
    # Exactly at threshold (exactly 3*365 days ago) -> No finding
    p_exact = mock_page("https://example.com/exact", page_type="product", date_candidates=[DateCandidate(exact_threshold_dt.strftime("%Y-%m-%d"), "json_ld", "datePublished")])
    
    # Just over threshold (1 day over threshold) -> Finding
    just_over_dt = exact_threshold_dt - datetime.timedelta(days=1)
    p_just_over = mock_page("https://example.com/just_over", page_type="product", date_candidates=[DateCandidate(just_over_dt.strftime("%Y-%m-%d"), "json_ld", "datePublished")])
    
    # Fresh product
    p_fresh = mock_page("https://example.com/fresh", page_type="product", date_candidates=[DateCandidate("2023-01-01", "json_ld", "datePublished")])
    
    ds = mock_dataset([p_stale, p_just_under, p_exact, p_just_over, p_fresh])
    findings = rule.evaluate(ds)
    
    assert len(findings) == 2
    urls = [f.evidence.page for f in findings]
    assert "https://example.com/stale" in urls
    assert "https://example.com/just_over" in urls
    assert_valid_finding(findings[0], ds)
