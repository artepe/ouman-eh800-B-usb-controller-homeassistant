"""Explicitly reviewed writable Ouflex points (never infer writes from Ounet access level).

The XML supplies a register address, data format and numeric range. It does NOT
prove that Modbus writes are permitted. A single named point can be unlocked in
an isolated laboratory through the Open HVAC options flow, tied to the exact
application map digest. No unknown coils, mode toggles or command registers.
"""
from __future__ import annotations

import math
from .profiles import Register


def candidates(native_points):
    """Human-reviewable numeric holding points; not automatically writable."""
    return [
        p for p in native_points
        if (p.entity == "sensor"
            and p.area == "holding"
            and p.kind in ("s16", "u16", "s32", "u32")
            and p.minimum is not None and p.maximum is not None
            and math.isfinite(p.minimum) and math.isfinite(p.maximum)
            and p.minimum < p.maximum
            and p.manual_reg is None
            and p.source
            and p.metadata.get("operation", "value") == "value"
            and p.metadata.get("pointtype") not in ("14", "15", "16", "17")
            and p.name)
    ]


def authorize(native_points, doc_digest, settings):
    """Return exactly one authorized candidate as HA Register or None.

    This is an operator-reviewed write/test facility; the source XML is
    always read-only evidence and cannot enable writes by itself.
    """
    if settings.get("ouflex_write_enabled") is not True:
        return None
    if settings.get("ouflex_write_isolated") is not True:
        return None
    if settings.get("ouflex_write_reviewed") is not True:
        return None
    if settings.get("ouflex_write_digest") != doc_digest:
        return None
    key = settings.get("ouflex_write_key")
    point = next((p for p in candidates(native_points) if p.key == key), None)
    if point is None:
        return None
    return Register(
        key=point.key, name=point.name, address=point.address,
        kind=point.kind, decimals=point.decimals, unit=point.unit,
        minimum=point.minimum, maximum=point.maximum,
        writable=True, area="holding",
    )
