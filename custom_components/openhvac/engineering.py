"""Read-only building energy and refrigerant cycle calculations.

No cloud access, controller commands, or refrigerant property assumptions.
All measurements must be independently verified.
"""
from __future__ import annotations
from math import isfinite


def finite(name: str, value: float) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a numeric measurement")
    try:
        number = float(value)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError(f"{name} must be a finite measurement") from exc
    if not isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def water_heating_power_kw(
    flow_m3_h: float, supply_c: float, return_c: float,
    *, density_kg_m3: float = 998.0, heat_capacity_kj_kg_k: float = 4.18
) -> float:
    """kW = m³/h * kg/m³ * kJ/(kg K) * K / 3600 (approximate water properties)."""
    flow, supply, ret = (
        finite("flow_m3_h", flow_m3_h),
        finite("supply_c", supply_c),
        finite("return_c", return_c),
    )
    density = finite("density_kg_m3", density_kg_m3)
    cp = finite("heat_capacity_kj_kg_k", heat_capacity_kj_kg_k)
    if not 0 < flow <= 1000 or not 0 < density <= 2000 or not 0 < cp <= 8:
        raise ValueError("Flow or fluid property outside valid range")
    if not -50 <= supply <= 130 or not -50 <= ret <= 130 or supply <= ret:
        raise ValueError("Heating output needs supply hotter than return")
    return flow * density * cp * (supply - ret) / 3600.0


def heating_cop(thermal_kw: float, electrical_kw: float) -> float:
    """Positive simultaneous heat/electric power; no seasonal averaging."""
    heat = finite("thermal_kw", thermal_kw)
    electric = finite("electrical_kw", electrical_kw)
    if heat <= 0 or electric <= 0:
        raise ValueError("COP requires positive simultaneous thermal and electrical power")
    return heat / electric


def refrigerant_cycle_heating_cop(
    suction_enthalpy_kj_kg: float,
    discharge_enthalpy_kj_kg: float,
    condenser_outlet_enthalpy_kj_kg: float,
) -> float:
    """Enthalpy-only cycle heating COP: Qcondenser / compressor enthalpy rise.

    This is a thermodynamic cycle estimate, NOT measured electrical COP.
    """
    h1 = finite("suction_enthalpy_kj_kg", suction_enthalpy_kj_kg)
    h2 = finite("discharge_enthalpy_kj_kg", discharge_enthalpy_kj_kg)
    h3 = finite("condenser_outlet_enthalpy_kj_kg",
                condenser_outlet_enthalpy_kj_kg)
    work = h2 - h1
    heat = h2 - h3
    if work <= 0 or heat <= 0 or heat < work:
        raise ValueError("Invalid enthalpy ordering for a heating cycle")
    return heat / work


def refrigerant_heating_power_kw(
    mass_flow_kg_s: float,
    discharge_enthalpy_kj_kg: float,
    condenser_outlet_enthalpy_kj_kg: float,
) -> float:
    mass = finite("mass_flow_kg_s", mass_flow_kg_s)
    h2 = finite("discharge_enthalpy_kj_kg", discharge_enthalpy_kj_kg)
    h3 = finite("condenser_outlet_enthalpy_kj_kg",
                condenser_outlet_enthalpy_kj_kg)
    if mass <= 0 or mass > 100 or h2 <= h3:
        raise ValueError("Invalid mass flow or condenser enthalpy drop")
    return mass * (h2 - h3)


def derive_cop_metrics(data: dict) -> dict[str, float]:
    """Read-only derived metrics from VERIFIED and correctly scaled input keys.

    flow_m3h, l1_supply, l1_return -> water kW
    electric_power_kw -> complete system electric input
    compressor_electric_power_kw -> compressor-only electric input
    refrigerant_{suction,discharge,liquid}_enthalpy_kj_kg -> cycle estimate
    refrigerant_mass_flow_kg_s -> refrigerant condenser heat
    No compressor-frequency-to-mass-flow guesses.
    """
    result: dict[str, float] = {}
    try:
        if all(k in data for k in ("flow_m3h", "l1_supply", "l1_return")):
            result["water_heating_power_kw"] = round(
                water_heating_power_kw(
                    data["flow_m3h"], data["l1_supply"], data["l1_return"]), 3)
    except ValueError:
        pass
    for input_key, output_key in (
        ("electric_power_kw", "system_heating_cop"),
        ("compressor_electric_power_kw", "water_compressor_heating_cop"),
    ):
        try:
            if "water_heating_power_kw" in result and input_key in data:
                result[output_key] = round(
                    heating_cop(result["water_heating_power_kw"], data[input_key]), 3)
        except ValueError:
            pass
    keys = (
        "refrigerant_suction_enthalpy_kj_kg",
        "refrigerant_discharge_enthalpy_kj_kg",
        "refrigerant_liquid_enthalpy_kj_kg",
    )
    if all(k in data for k in keys):
        try:
            result["refrigerant_cycle_heating_cop_estimate"] = round(
                refrigerant_cycle_heating_cop(*(data[k] for k in keys)), 3)
        except ValueError:
            pass
    if all(k in data for k in (
        "refrigerant_mass_flow_kg_s",
        "refrigerant_discharge_enthalpy_kj_kg",
        "refrigerant_liquid_enthalpy_kj_kg",
    )):
        try:
            result["refrigerant_heating_power_kw"] = round(
                refrigerant_heating_power_kw(
                    data["refrigerant_mass_flow_kg_s"],
                    data["refrigerant_discharge_enthalpy_kj_kg"],
                    data["refrigerant_liquid_enthalpy_kj_kg"]), 3)
        except ValueError:
            pass
    try:
        if ("refrigerant_heating_power_kw" in result
                and "compressor_electric_power_kw" in data):
            result["refrigerant_compressor_heating_cop"] = round(
                heating_cop(result["refrigerant_heating_power_kw"],
                            data["compressor_electric_power_kw"]), 3)
    except ValueError:
        pass
    return result
