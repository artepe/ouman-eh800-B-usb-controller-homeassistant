"""Pure, non-controlling plant calculations for the HA dashboard."""
from __future__ import annotations
from math import isfinite


def _number(data: dict, key: str):
    value = data.get(key)
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
        return result if isfinite(result) else None
    except (ValueError, TypeError):
        return None


def derive_plant_metrics(data: dict) -> dict[str, float]:
    """Only derive values where exact, already-decoded signals exist.

    Water only. kW=1.163 * m³/h * K. Glycol requires its own fluid factor.
    """
    metrics = {}
    supply = _number(data, "l1_supply")
    ret = _number(data, "l1_return")
    flow = _number(data, "flow_m3h")
    if supply is not None and ret is not None:
        delta = round(supply - ret, 3)
        metrics["l1_delta_t"] = delta
        if flow is not None and 0 <= flow <= 100:
            metrics["l1_thermal_power_kw"] = round(1.163 * flow * delta, 3)
    return metrics


def diagnostic_notes(data: dict) -> list[str]:
    """Explain possible anomalies, never claim a fault diagnosis as fact."""
    m = derive_plant_metrics(data)
    notes = []
    dt = m.get("l1_delta_t")
    if dt is not None and dt < -2:
        notes.append("L1 menovesi on yli 2 °C paluuta kylmempi: tarkista anturit ja virtaussuunta")
    if dt is not None and dt > 25:
        notes.append("L1 meno-/paluulämpötilaero ylittää 25 °C: tarkista virtaus ja mittaukset")
    target = _number(data, "l1_supply_target")
    supply = _number(data, "l1_supply")
    if target is not None and supply is not None and abs(target - supply) > 15:
        notes.append("L1 menovesi poikkeaa yli 15 °C pyynnistä: tarkista lämmönlähde ja venttiili")
    return notes
