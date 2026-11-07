"""Time helpers. The API speaks epoch milliseconds; reports use IST calendar days."""

from datetime import datetime, timedelta, timezone as dt_timezone

from django.utils import timezone
from django.utils.dateparse import parse_datetime

# Anything below this is read as epoch *seconds* (1e11 s is year 5138; 1e11 ms is 1973).
_SECONDS_LIMIT = 1e11


def to_ms(value):
    """aware datetime -> epoch ms (None stays None)."""
    if value is None:
        return None
    return int(value.timestamp() * 1000)


def from_ms(ms):
    return datetime.fromtimestamp(ms / 1000, tz=dt_timezone.utc)


def parse_timestamp(value):
    """Epoch seconds, epoch milliseconds or an ISO 8601 string -> aware UTC datetime."""
    if isinstance(value, bool):
        raise ValueError("timestamp must be a number or ISO string")
    if isinstance(value, (int, float)):
        if value != value or value in (float("inf"), float("-inf")):
            raise ValueError("timestamp is not finite")
        seconds = value if abs(value) < _SECONDS_LIMIT else value / 1000
        return datetime.fromtimestamp(seconds, tz=dt_timezone.utc)
    if isinstance(value, str):
        text = value.strip()
        if text.replace(".", "", 1).isdigit():
            return parse_timestamp(float(text))
        parsed = parse_datetime(text)
        if parsed is None:
            raise ValueError("timestamp is not a valid ISO 8601 date")
        if timezone.is_naive(parsed):
            parsed = parsed.replace(tzinfo=dt_timezone.utc)
        return parsed.astimezone(dt_timezone.utc)
    raise ValueError("timestamp must be a number or ISO string")


def local_hour_start(dt):
    """Start of the IST hour containing `dt` (aware)."""
    return timezone.localtime(dt).replace(minute=0, second=0, microsecond=0)


def local_day_start(dt, days_back=0):
    """Start of the IST day containing `dt`, optionally `days_back` days earlier."""
    start = timezone.localtime(dt).replace(hour=0, minute=0, second=0, microsecond=0)
    return start - timedelta(days=days_back)
