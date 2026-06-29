"""backend/utils.py
==================
Shared helpers used across multiple route modules.
"""

from __future__ import annotations

from datetime import date, datetime


def serialize(obj):
    """Recursively convert date/datetime objects to ISO strings for JSON serialisation."""
    if isinstance(obj, dict):
        return {k: serialize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [serialize(v) for v in obj]
    if isinstance(obj, (date, datetime)):
        return str(obj)
    return obj
