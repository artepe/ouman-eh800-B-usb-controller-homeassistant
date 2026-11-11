"""Operator-reviewed Ouflex setpoints for Home Assistant's Open HVAC Bridge.

The controller's XML map provides candidate addresses and numeric ranges, NOT
authorization to write. Each selected point must be independently checked on
the actual, isolated application. The selection is bound to the exact XML
digest, so changes to the controller's application disable all writes.
"""
from __future__ import annotations

import math

from .profiles import Register


def candidates(native_points):
    """Candidates for UI review; never imply FC06/FC16 support."""
    result = []
    for point in native_points:
        if (point.entity != "sensor"
                or point.area != "holding"
                or point.kind not in ("s16", "u16", "s32", "u32")
                or point.minimum is None or point.maximum is None
                or not math.isfinite(point.minimum)
                or not math.isfinite(point.maximum)
                or point.minimum >= point.maximum
                or point.manual_reg is not None
                or not point.source or not point.name
                or point.metadata.get("operation", "value") != "value"
                or point.metadata.get("pointtype") in ("5", "8", "9", "11", "14", "15", "16", "17")
                or point.decimals > 5):
            continue
        result.append(point)
    return result


def selected_keys(settings):
    """Backward-compatible migration from original single-number option."""
    keys = settings.get("ouflex_write_keys")
    if keys is None:
        key = settings.get("ouflex_write_key", "")
        keys = [key] if key else []
    if not isinstance(keys, list) or not all(isinstance(k, str) for k in keys):
        return []
    # Stable order and no duplicate keys.
    return list(dict.fromkeys(keys))


def authorize(native_points, doc_digest, settings):
    """Map of authorized HA number controls, empty unless all gates pass."""
    if (settings.get("ouflex_write_enabled") is not True
            or settings.get("ouflex_write_isolated") is not True
            or settings.get("ouflex_write_reviewed") is not True
            or settings.get("ouflex_write_digest") != doc_digest):
        return {}
    selectable = {p.key: p for p in candidates(native_points)}
    selected = selected_keys(settings)
    if not selected or any(k not in selectable for k in selected):
        return {}
    result = {}
    for key in selected:
        p = selectable[key]
        # Ounet XML's access field is retained as metadata. This control is
        # unlocked only by explicit operator review, not metadata alone.
        result[key] = Register(
            key=p.key, name=p.name, address=p.address,
            kind=p.kind, decimals=p.decimals, unit=p.unit,
            minimum=p.minimum, maximum=p.maximum,
            writable=True, area="holding",
        )
    return result
