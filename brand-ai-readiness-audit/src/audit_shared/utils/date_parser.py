import datetime
from typing import Optional, Tuple
import re

def parse_date_with_status(value: str) -> Tuple[Optional[datetime.datetime], str]:
    """
    Deterministically parses a date string into a timezone-aware UTC datetime.
    Returns (dt, status).
    status can be: 'VALID', 'UNPARSEABLE', 'IMPOSSIBLE'
    """
    if not isinstance(value, str):
        return None, 'UNPARSEABLE'
    
    value = value.strip()
    if not value:
        return None, 'UNPARSEABLE'

    # Handle standard 'Z' for UTC
    original_value = value
    if value.endswith('Z'):
        value = value[:-1] + '+00:00'

    try:
        dt = datetime.datetime.fromisoformat(value)
    except ValueError:
        # Check if it looks like a calendar date but is impossible (e.g., 2024-02-30)
        # Basic regex to catch YYYY-MM-DD that failed fromisoformat
        if re.match(r'^\d{4}-\d{2}-\d{2}', value):
            return None, 'IMPOSSIBLE'
        return None, 'UNPARSEABLE'

    # If it's a naive datetime, assume UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    else:
        # Convert to UTC
        dt = dt.astimezone(datetime.timezone.utc)

    return dt, 'VALID'

def parse_date(value: str) -> Optional[datetime.datetime]:
    dt, _ = parse_date_with_status(value)
    return dt

def is_calendar_impossible(dt: datetime.datetime) -> bool:
    """
    Checks if a datetime represents an impossible calendar date.
    (Note: python's fromisoformat already rejects things like 2024-02-30.
    But if we need specific manual boundaries we could put them here).
    For now, fromisoformat failing covers calendar impossibilities.
    """
    return False

def is_future_date(dt: datetime.datetime, audit_time: datetime.datetime, tolerance_hours: int = 24) -> bool:
    """
    Checks if the date is in the future relative to the canonical audit time.
    Uses a 24-hour tolerance to account for timezone bleed.
    """
    limit = audit_time + datetime.timedelta(hours=tolerance_hours)
    return dt > limit

def are_dates_equivalent(dt1: datetime.datetime, dt2: datetime.datetime) -> bool:
    """
    Exact timestamp equality or timezone-equivalent timestamp.
    Since parse_date converts all to UTC, we can just do equality.
    """
    return dt1 == dt2

def are_same_utc_calendar_day(dt1: datetime.datetime, dt2: datetime.datetime) -> bool:
    """
    Checks if two datetimes fall on the same UTC calendar day.
    """
    return dt1.date() == dt2.date()

def date_diff_hours(dt_early: datetime.datetime, dt_late: datetime.datetime) -> float:
    """
    Returns the difference in hours between two dates (dt_late - dt_early).
    """
    delta = dt_late - dt_early
    return delta.total_seconds() / 3600.0

def is_valid_chronology(published: datetime.datetime, modified: datetime.datetime, tolerance_hours: int = 24) -> bool:
    """
    Published <= Modified is normal.
    We allow published to be up to `tolerance_hours` AFTER modified due to timezone/batch updates.
    Returns True if chronology is valid, False if it is a deterministically invalid chronology.
    """
    if published <= modified:
        return True
    
    # If published is after modified, check if it's within the tolerance.
    diff = date_diff_hours(modified, published)
    if diff <= tolerance_hours:
        return True
        
    return False
