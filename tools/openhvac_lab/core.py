"""Common validated measurements and timing helpers for OpenHVAC Lab."""
from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite
from statistics import median


class InvalidMeasurement(ValueError):
    """A measurement cannot be trusted or used in a calculation."""


def number(value, name="value", *, minimum=None, maximum=None):
    """Require a finite numeric input; reject bool and missing values."""
    if value is None or isinstance(value, bool):
        raise InvalidMeasurement(f"{name}: missing or non-numeric")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise InvalidMeasurement(f"{name}: invalid number") from exc
    if not isfinite(result):
        raise InvalidMeasurement(f"{name}: not finite")
    if minimum is not None and result < minimum:
        raise InvalidMeasurement(f"{name}: below accepted lower bound")
    if maximum is not None and result > maximum:
        raise InvalidMeasurement(f"{name}: above accepted upper bound")
    return result


def optional_number(row, key, *, minimum=None, maximum=None):
    try:
        return number(row.get(key), key, minimum=minimum, maximum=maximum)
    except (InvalidMeasurement, AttributeError):
        return None


def utc_time(value):
    """Parse a timezone-aware datetime or ISO8601 string, normalized to UTC."""
    if isinstance(value, datetime):
        out = value
    elif isinstance(value, str):
        try:
            out = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise InvalidMeasurement("timestamp must be valid ISO8601") from exc
    else:
        raise InvalidMeasurement("timestamp is required")
    if out.tzinfo is None:
        raise InvalidMeasurement("timestamp must contain an explicit timezone")
    return out.astimezone(timezone.utc)


def iso(value):
    return utc_time(value).isoformat().replace("+00:00", "Z")


def baseline(values, *, minimum_samples=5):
    """Robust median + absolute median deviation; no trained-model claims."""
    series = []
    for value in values:
        try:
            series.append(number(value))
        except InvalidMeasurement:
            continue
    if len(series) < minimum_samples:
        return None
    midpoint = median(series)
    return {
        "samples": len(series),
        "median": round(midpoint, 5),
        "median_absolute_deviation": round(
            median(abs(item - midpoint) for item in series), 5),
    }


def finding(code, severity, summary, evidence, *, recommendation, confidence="conditional"):
    if severity not in {"info", "warning", "critical"}:
        raise ValueError("Invalid severity")
    return {
        "code": code,
        "severity": severity,
        "summary": summary,
        "evidence": evidence,
        "recommendation": recommendation,
        "confidence": confidence,
        "commands_issued": 0,
    }
