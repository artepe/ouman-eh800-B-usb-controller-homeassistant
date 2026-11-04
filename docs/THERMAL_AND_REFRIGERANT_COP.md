# Thermal / refrigerant COP and CO2 supplemental ventilation

## Water-side heat and COP

For water (not glycol), approximate heating power:

    heat_kW = flow_m3h * density_kg_m3 * cp_kJ_per_kgK
              * (supply_C - return_C) / 3600

Defaults in the read-only calculator: water density 998 kg/m3,
heat capacity 4.18 kJ/kg K; conversion factor about 1.159.
The common 1.163 factor is another water-properties approximation.
Flow calibration, return/supply sensor placement and timestamps matter.

    whole_system_COP = water_heat_kW / whole_system_electrical_kW
    compressor_input_COP = water_heat_kW / compressor_electrical_kW

These have different electric measurement boundaries. Compressor-only
input excludes some pumps/controls/fans, possibly including defrost.
For daily/seasonal COP integrate heat and electricity in kWh over
the same time window, not average instantaneous ratios.

Read-only custom point keys:
flow_m3h, l1_supply, l1_return, electric_power_kw,
compressor_electric_power_kw.

## Refrigerant thermodynamic cycle COP

    cycle_heating_COP = (h_discharge - h_condenser_out)
                        / (h_discharge - h_suction)

This is a **theoretical cycle estimate**, not measured electrical COP.
Correct refrigerant and actual thermodynamic state/phase are needed.
Compressor RPM, EEV position, temperature alone and uncalibrated pressure
do not determine h1/h2/h3.

With **measured refrigerant mass flow**, not a guessed surrogate:

    refrigerant_condenser_kW =
        refrigerant_mass_flow_kg_s * (h_discharge - h_condenser_out)
    refrigerant_compressor_electrical_COP =
        refrigerant_condenser_kW / compressor_electric_kw

Additional verified source keys:
refrigerant_suction_enthalpy_kj_kg,
refrigerant_discharge_enthalpy_kj_kg,
refrigerant_liquid_enthalpy_kj_kg,
refrigerant_mass_flow_kg_s.

R290 is propane. If using property software (e.g. CoolProp), ensure
the **correct fluid, absolute not gauge pressure**, calibrated line
temperatures, vapor/liquid phase and simultaneous snapshots. No
entire refrigeration performance can be inferred from suction
superheat alone. No automatic refrigerant EEV/controller writes.

Examples for HA:
- ../examples/homeassistant/openhvac-water-cop-package.yaml
- ../examples/homeassistant/openhvac-refrigerant-cop-package.yaml

## Optional R290 property calculator

If you can measure three simultaneous refrigerant states
(absolute pressure and line temperature at suction, discharge and
condenser liquid outlet), use the offline diagnostics script:

    python3 -m pip install CoolProp
    python3 tools/refrigerant_state_calculator.py --fluid R290 \
      --suction-bar-a 4 --suction-c 3 \
      --discharge-bar-a 17 --discharge-c 90 \
      --liquid-bar-a 17 --liquid-c 45

**Sample numbers are fictitious** and must not be treated as a
known-good R290 charge, pressure target or heating curve.
The script does no actuator output, external network traffic or
Home Assistant state changes. Without measured refrigerant mass flow,
it does not report actual refrigerant heat power or electrical COP.

## CO2 supplemental 0-10 V ventilation fan

HA auxiliary fan blueprint:
../blueprints/automation/openhvac/co2_supplemental_fan_0_10v.yaml

Separate persistent high-CO2 alert blueprint (no control actions):
../blueprints/automation/openhvac/co2_high_alert.yaml

Example Lovelace fan/CO2 monitoring card:
../examples/lovelace-openhvac-co2-fan.yaml

Configure indoor CO2, outdoor temperature, Shelly dimmable auxiliary fan
(light entity) and an input_boolean automatic-enable helper.

Defaults: CO2 650-1400 ppm linearly maps to 20%-100% fan demand.
Below outdoor 6 C, the **auxiliary** fan stops with 1 C restart
hysteresis and 5 percentage-point speed change deadband. If sensor
readings are invalid/missing, no output command is sent. Disabling
the helper leaves manual fan operation alone.

**Never use this example to disable legally required ventilation,
smoke evacuation or native frost/fire protections.** Check voltage,
EC motor speed floor and code-required minimum ventilation. The
cutout is meant only for a separately approved auxiliary roof fan.

To install on HA OS:
    /config/blueprints/automation/openhvac/co2_supplemental_fan_0_10v.yaml

Create a new automation from the blueprint in HA and select the
actual entities. Committing the example does not install it in HA.

## Further diagnostics for real sites

- Refrigerant superheat/subcooling from validated absolute pressure
  and saturation thermodynamic state.
- Heat exchanger temperature effectiveness and district heat return.
- Stratified buffer storage monitoring and thermal storage kWh.
- CO2 high-state persistent alerts; sensor staleness; VAV pressure.
- Water-leak and low-pressure maintenance alerts.
- Separate compressor, pumps, fans and backup resistance electricity.
- Per-site alarms and event history without disabling OEM safeties.

Experimental only: no certified controller and no physical validation
of every vendor port or energy sensor.
