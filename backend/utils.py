"""Small shared helpers."""
from datetime import datetime, timezone


def utcnow() -> datetime:
    """Naive UTC timestamp.

    Replaces the deprecated datetime.utcnow(). We intentionally strip tzinfo so
    values stay consistent with the naive UTC datetimes already stored in the
    database (mixing aware/naive datetimes raises on comparison).
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)
