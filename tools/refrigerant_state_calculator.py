#!/usr/bin/env python3
"""Optional offline refrigerant enthalpy/COP diagnostic using CoolProp.

Does NOT install a Home Assistant integration, change HVAC settings or
connect to controllers. Uses absolute pressures (bar absolute), never
unqualified gauge pressure. Refrigerant fluid and P/T measurements
must be independently verified. Thermodynamic COP is not electric COP.

Optional dependency: python3 -m pip install CoolProp
Example:
python tools/refrigerant_state_calculator.py \
  --fluid R290 --suction-bar-a 4 --suction-c 3 \
  --discharge-bar-a 17 --discharge-c 90 \
  --liquid-bar-a 17 --liquid-c 45
"""
from __future__ import annotations

import argparse
import json
from math import isfinite
import sys

from pathlib import Path

if __package__:
    from custom_components.openlvi.engineering import (
        refrigerant_cycle_heating_cop, refrigerant_heating_power_kw, heating_cop
    )
else:
    import importlib.util
    _ROOT = Path(__file__).resolve().parents[1]
    _SOURCE = _ROOT / "custom_components" / "openlvi" / "engineering.py"
    spec = importlib.util.spec_from_file_location("openlvi_engineering_standalone", _SOURCE)
    eng = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(eng)
    refrigerant_cycle_heating_cop = eng.refrigerant_cycle_heating_cop
    refrigerant_heating_power_kw = eng.refrigerant_heating_power_kw
    heating_cop = eng.heating_cop

SUPPORTED_FLUIDS = frozenset(("R290", "R32", "R410A", "R134a", "R407C", "R744"))


def _verified_number(name, value, minimum, maximum):
    if isinstance(value, bool):
        raise ValueError(f"Invalid {name}")
    try:
        v = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"Invalid {name}") from exc
    if not isfinite(v) or v < minimum or v > maximum:
        raise ValueError(f"Out of range {name}")
    return v


def calculate(
    fluid, suction_bar_abs, suction_c, discharge_bar_abs, discharge_c,
    liquid_bar_abs, liquid_c, *, mass_flow_kg_s=None,
    compressor_electric_kw=None, props=None,
):
    """Evaluate three steady-state enthalpies using optional CoolProp PropsSI.

    PropsSI callable can be injected for offline deterministic unit tests.
    """
    if fluid not in SUPPORTED_FLUIDS:
        raise ValueError("Refrigerant must be a supported explicit fluid")
    pressures = [
        _verified_number("suction bar absolute", suction_bar_abs, 0.05, 150),
        _verified_number("discharge bar absolute", discharge_bar_abs, 0.05, 150),
        _verified_number("condenser liquid bar absolute", liquid_bar_abs, 0.05, 150),
    ]
    temps = [
        _verified_number("suction temperature C", suction_c, -100, 200),
        _verified_number("discharge temperature C", discharge_c, -100, 200),
        _verified_number("liquid temperature C", liquid_c, -100, 200),
    ]
    if pressures[1] <= pressures[0] or pressures[2] <= pressures[0]:
        raise ValueError("High-side pressures must exceed suction pressure")
    if mass_flow_kg_s is not None:
        mass_flow_kg_s = _verified_number("measured mass flow", mass_flow_kg_s,
                                         0.000001, 100)
    if compressor_electric_kw is not None:
        compressor_electric_kw = _verified_number(
            "measured compressor electric kW", compressor_electric_kw,
            0.000001, 1000)
    if props is None:
        try:
            from CoolProp.CoolProp import PropsSI
        except ImportError as exc:
            raise RuntimeError(
                "Optional CoolProp is required: python3 -m pip install CoolProp"
            ) from exc
        props = PropsSI

    try:
        h = [
            props("H", "P", p * 100000.0, "T", t + 273.15, fluid) / 1000.0
            for p, t in zip(pressures, temps)
        ]
        sat_evap_dew_c = (
            props("T", "P", pressures[0] * 100000.0, "Q", 1, fluid) - 273.15
        )
        sat_cond_bubble_c = (
            props("T", "P", pressures[2] * 100000.0, "Q", 0, fluid) - 273.15
        )
    except Exception as exc:
        raise ValueError(f"Refrigerant state calculation failed: {exc}") from exc

    if not all(isfinite(v) for v in (*h, sat_evap_dew_c, sat_cond_bubble_c)):
        raise ValueError("Invalid fluid property output")

    # P and T only fix the state of a single-phase fluid. Without superheat
    # or subcooling the measured point may be two-phase (or the pressure was
    # gauge, not absolute) and the enthalpy would be meaningless.
    superheat_k = temps[0] - sat_evap_dew_c
    subcooling_k = sat_cond_bubble_c - temps[2]
    if superheat_k <= 0:
        raise ValueError(
            f"Suction is not superheated vapour (superheat {superheat_k:.1f} K): "
            "check the suction sensor position and that pressure is absolute")
    if subcooling_k <= 0:
        raise ValueError(
            f"Condenser outlet is not subcooled liquid (subcooling {subcooling_k:.1f} K): "
            "check the liquid-line sensor and that pressure is absolute")

    result = {
        "fluid": fluid,
        "status": "unverified_input_thermodynamic_estimate_only",
        "enthalpy_suction_kj_kg": round(h[0], 3),
        "enthalpy_discharge_kj_kg": round(h[1], 3),
        "enthalpy_condenser_out_kj_kg": round(h[2], 3),
        "superheat_k": round(superheat_k, 2),
        "subcooling_k": round(subcooling_k, 2),
        "cycle_heating_cop_estimate": round(
            refrigerant_cycle_heating_cop(*h), 3),
    }
    if mass_flow_kg_s is not None:
        ref_kw = refrigerant_heating_power_kw(mass_flow_kg_s, h[1], h[2])
        result["condenser_thermal_kw"] = round(ref_kw, 3)
        if compressor_electric_kw is not None:
            result["compressor_electrical_heating_cop"] = round(
                heating_cop(ref_kw, compressor_electric_kw), 3)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fluid", default="R290", choices=sorted(SUPPORTED_FLUIDS))
    for point in ("suction", "discharge", "liquid"):
        parser.add_argument(f"--{point}-bar-a", required=True, type=float,
                            help="ABSOLUTE pressure, not gauge pressure")
        parser.add_argument(f"--{point}-c", required=True, type=float)
    parser.add_argument("--mass-flow-kg-s", type=float,
                        help="Measured refrigerant mass flow; never guessed")
    parser.add_argument("--compressor-electric-kw", type=float,
                        help="Measured electrical compressor input")
    args = parser.parse_args(argv)
    try:
        result = calculate(
            args.fluid, args.suction_bar_a, args.suction_c,
            args.discharge_bar_a, args.discharge_c,
            args.liquid_bar_a, args.liquid_c,
            mass_flow_kg_s=args.mass_flow_kg_s,
            compressor_electric_kw=args.compressor_electric_kw,
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except (ValueError, RuntimeError) as exc:
        print(f"OpenLVI: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
