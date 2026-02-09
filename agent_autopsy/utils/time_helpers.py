"""Utilities for time parsing and duration calculations."""

from datetime import datetime, timezone
from typing import Optional


def parse_iso_timestamp(value: Optional[str]) -> Optional[datetime]:
    """Parse an ISO 8601 timestamp string into a timezone-aware datetime."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def duration_ms(start: Optional[datetime], end: Optional[datetime]) -> Optional[float]:
    """Calculate duration in milliseconds between two datetimes."""
    if start is None or end is None:
        return None
    return (end - start).total_seconds() * 1000


def is_before(a: Optional[datetime], b: Optional[datetime]) -> bool:
    """Check if datetime a is before datetime b. Returns False if either is None."""
    if a is None or b is None:
        return False
    return a < b


def spans_overlap(
    start_a: Optional[datetime],
    end_a: Optional[datetime],
    start_b: Optional[datetime],
    end_b: Optional[datetime],
) -> bool:
    """Check if two time ranges overlap."""
    if any(t is None for t in (start_a, end_a, start_b, end_b)):
        return False
    return start_a < end_b and start_b < end_a  # type: ignore[operator]
