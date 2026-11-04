"""Explainable fault heuristics and rolling reference baselines.

Fault candidates are never presented as confirmed mechanical diagnoses.
"""
from __future__ import annotations
from statistics import median
from .core import baseline, finding, number, optional_number, InvalidMeasurement


def _valid_series(history, key, minimum=5):
    if not isinstance(history, list) or len(history) > 10000:
        raise ValueError("Expected up to 10000 historical samples")
    return [v for row in history if isinstance(row, dict)
            if (v := optional_number(row, key)) is not None]


def analyze_plant(current, history=None):
    """Return evidence-backed observations; read-only, no setpoint commands."""
    if not isinstance(current, dict):
        raise ValueError("Current measurements must be a JSON object")
    history = history or []
    if not isinstance(history, list) or len(history) > 10000:
        raise ValueError("History must be a list of at most 10000 samples")
    findings = []
    hints = []

    heat = optional_number(current, "heating_power_kw", minimum=0)
    electric = optional_number(current, "electric_power_kw", minimum=0)
    cop = optional_number(current, "heating_cop", minimum=0)
    if cop is None and heat is not None and electric and electric > 0:
        cop = heat / electric
    if cop is not None:
        reference = baseline(_valid_series(history, "heating_cop"))
        if reference:
            typical = reference["median"]
            spread = reference["median_absolute_deviation"]
            if typical > 0 and typical - cop > max(0.7, typical * .22, spread * 3):
                findings.append(finding(
                    "cop_decline", "warning",
                    "Heating COP is below the historical reference.",
                    {"cop_now": round(cop, 2), "reference_median": typical,
                     "reference_samples": reference["samples"]},
                    recommendation="Compare outdoor temperature, defrost, load and power metering before diagnosing the heat pump."))
        else:
            hints.append("A COP trend needs at least 5 validated reference samples.")

    valve = optional_number(current, "valve_position_pct", minimum=0, maximum=100)
    supply = optional_number(current, "supply_c", minimum=-50, maximum=130)
    setpoint = optional_number(current, "supply_target_c", minimum=-50, maximum=130)
    if valve is not None and supply is not None and setpoint is not None:
        if valve >= 92 and setpoint - supply > 7:
            findings.append(finding(
                "unmet_supply_target", "warning",
                "Valve near fully open while supply remains below target.",
                {"valve_pct": valve, "supply_c": supply, "target_c": setpoint},
                recommendation="Check heat-source capacity, flow, sensors and valve response. Do not override the controller."))

    dp = optional_number(current, "filter_pressure_pa", minimum=0)
    allowed_dp = optional_number(current, "filter_limit_pa", minimum=1)
    if dp is not None and allowed_dp is not None and dp >= allowed_dp:
        findings.append(finding(
            "filter_pressure", "warning", "Filter pressure loss exceeds the supplied maintenance limit.",
            {"pressure_pa": dp, "site_limit_pa": allowed_dp},
            recommendation="Check filter loading, airflow and the actual pressure sensor."))

    flow = optional_number(current, "water_flow_m3h", minimum=0)
    requested_min = optional_number(current, "min_expected_flow_m3h", minimum=0)
    if (flow is not None and requested_min is not None
            and flow < requested_min and (heat is None or heat > 0)):
        findings.append(finding(
            "low_flow", "warning", "Water flow is below the site-defined minimum.",
            {"flow_m3h": flow, "site_minimum_m3h": requested_min},
            recommendation="Verify sensor, strainer, circulation pump and balancing valves."))

    if isinstance(history, list) and history:
        window = history[-min(120, len(history)):]
        states = [row.get("defrost_active") for row in window if isinstance(row, dict)]
        if len(states) >= 12 and all(isinstance(v, bool) for v in states):
            transitions = sum(
                not a and b for a, b in zip(states, states[1:]))
            if transitions >= 5:
                findings.append(finding(
                    "frequent_defrost", "info",
                    "Multiple defrost events appeared in the selected observation window.",
                    {"starts_in_window": transitions, "samples_in_window": len(states)},
                    recommendation="Verify timestamps/sample interval, actual frost conditions and refrigerant sensor quality."))

    return {
        "algorithm": "explainable_rules_and_robust_reference",
        "findings": findings,
        "notes": hints,
        "verified_root_cause": False,
        "commands_issued": 0,
    }
