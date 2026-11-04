"""Ventilation recovery, airflow and demand indicators; no fan commands."""
from __future__ import annotations
from .core import number, optional_number


def assess_ventilation(data):
    if not isinstance(data, dict):
        raise ValueError("ventilation measurements must be an object")
    outdoor = optional_number(data, "outdoor_c", minimum=-60, maximum=55)
    supply = optional_number(data, "supply_c", minimum=-40, maximum=70)
    extract = optional_number(data, "extract_c", minimum=-20, maximum=70)
    flow_m3h = optional_number(data, "supply_airflow_m3h", minimum=0, maximum=100000)
    elec_kw = optional_number(data, "fan_electric_kw", minimum=0, maximum=10000)
    co2 = optional_number(data, "co2_ppm", minimum=300, maximum=10000)
    result = {"metrics": {}, "warnings": [], "commands_issued": 0}
    if outdoor is not None and supply is not None and extract is not None:
        delta = extract - outdoor
        if abs(delta) >= 2.0:
            efficiency = (supply - outdoor) / delta
            result["metrics"]["temperature_recovery_ratio"] = round(efficiency, 3)
            if efficiency < -0.1 or efficiency > 1.1:
                result["warnings"].append(
                    "Temperature ratio outside usual range: validate sensor locations, active heating/cooling and bypass.")
            # Approximate sensible heating recovery, NOT measured EN 308 efficiency.
            if flow_m3h is not None and flow_m3h > 0:
                recovery_kw = flow_m3h * 1.2 * 1.005 * (supply - outdoor) / 3600
                result["metrics"]["estimated_sensible_recovery_kw"] = round(recovery_kw, 3)
        else:
            result["warnings"].append(
                "Cannot estimate temperature recovery when outdoor and extract air temperatures are close.")
    if flow_m3h is not None and flow_m3h > 0 and elec_kw is not None:
        result["metrics"]["estimated_sfp_kw_per_m3s"] = round(
            elec_kw / (flow_m3h / 3600), 3)
    if co2 is not None:
        result["metrics"]["co2_ppm"] = co2
        if co2 > 1500:
            result["warnings"].append(
                "Elevated CO2 requires occupancy, outdoor air and airflow checks.")
    result["warnings"].append(
        "Estimates exclude fan heat, leakage, recirculation, frost protection and separate post-heating.")
    return result
