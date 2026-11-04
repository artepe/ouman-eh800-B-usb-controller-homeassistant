"""No-cloud HVAC integration path catalog and read-only HA state normalizer.

This module NEVER connects to vendor servers, serial interfaces, HVAC controllers
or HA APIs. It consumes already available Home Assistant measurements.
"""
from __future__ import annotations
from .core import number, utc_time, iso, InvalidMeasurement

# (name, protocol, ordinary runtime, setup requirements, upstream reference)
PATHS = {
    "panasonic_comfort_cloud": ("Panasonic Comfort Cloud", "vendor_cloud",
        "cloud_required", "Panasonic account/2FA",
        "https://github.com/sockless-coding/panasonic_cc"),
    "panasonic_aquarea_smart_cloud": ("Panasonic Aquarea Smart Cloud", "vendor_cloud",
        "cloud_required", "Aquarea cloud account",
        "https://www.aircon.panasonic.eu/"),
    "panasonic_split_esphome": ("Panasonic split AC CN-CNT", "esp_uart",
        "local", "Compatible CN-CNT/CN-WLAN ESP32 and isolated level interface",
        "https://github.com/DomiStyle/esphome-panasonic-ac"),
    "panasonic_aquarea_heishamon": ("Panasonic Aquarea H/J/K/L/M", "mqtt_local",
        "local", "Compatible HeishaMon PCB on appropriate CN-CNT/CN-NMODE bus",
        "https://github.com/HeishaMon/HeishaMon"),
    "panasonic_aquarea_m_modbus": ("Panasonic Aquarea M series", "modbus_rtu",
        "local", "M-series-compatible CZ-NSMB expansion, verified RS485 map",
        "https://community.home-assistant.io/t/panasonic-aquarera-m-series-local-integration/973612"),
    "mango_r290_tuya_local": ("Mango R290 OEM", "tuya_lan",
        "local", "Supported Wi-Fi firmware, owned local device key, device ID and LAN IP",
        "https://github.com/Korkuttum/tuya_heat_pump"),
    "chinese_oem_tuya_local": ("Chinese OEM Wi-Fi heat pump", "tuya_lan",
        "local", "Verified per-model Tuya datapoints, legitimate local key and LAN",
        "https://github.com/make-all/tuya-local"),
    "chinese_oem_modbus": ("Chinese OEM air-water heat pump", "modbus_rtu",
        "local", "Isolated RS485 and official exact-model/firmware register map",
        "https://www.home-assistant.io/integrations/modbus/"),
    "midea_msmart_local": ("Midea M-Smart compatible", "midea_lan",
        "local", "Compatible M-Smart hardware; V3 token/key may need cloud once",
        "https://www.home-assistant.io/integrations/midea"),
    "gree_lan": ("Gree-compatible AC", "gree_lan",
        "local", "Supported Wi-Fi module, may require Gree+ initial network pairing",
        "https://www.home-assistant.io/integrations/gree"),
    "mitsubishi_ecodan_cn105": ("Mitsubishi Ecodan FTC", "esp_uart",
        "local", "Verified Ecodan CN105 ESPHome hardware/firmware",
        "https://github.com/gekkekoe/esphome-ecodan-hp"),
    "daikin_lan": ("Daikin compatible BRP", "daikin_lan",
        "local", "Verified BRP controller with local interface, not all ONECTA models",
        "https://www.home-assistant.io/integrations/daikin"),
}
# Strictly typed, never auto-map an unknown Tuya DP to any HVAC control.
UNIT_MAP = {
    "outdoor_c": ("°C",), "room_c": ("°C",), "supply_c": ("°C",),
    "return_c": ("°C",), "dhw_c": ("°C",), "target_c": ("°C",),
    "refrigerant_suction_c": ("°C",), "refrigerant_discharge_c": ("°C",),
    "coil_c": ("°C",), "water_flow_m3h": ("m³/h", "L/h", "L/min"),
    "electric_power_kw": ("kW", "W"), "thermal_power_kw": ("kW", "W"),
    "compressor_frequency_hz": ("Hz",), "compressor_speed_rps": ("rps",),
    "refrigerant_high_pressure_bar_abs": ("bar",),
    "refrigerant_low_pressure_bar_abs": ("bar",),
    "co2_ppm": ("ppm",),
    "defrost_active": ("boolean",), "alarm_active": ("boolean",),
}

def plan_local_path(path_id, *, physical_interface_verified=False,
                    verified_wan_offline=False):
    """Classify source honestly: local at runtime is not cloud-free onboarding."""
    if path_id not in PATHS:
        raise ValueError("Unknown model: no generic heat pump protocol assumed")
    name, protocol, runtime, setup, url = PATHS[path_id]
    cloud_required = runtime == "cloud_required"
    return {
        "path": path_id, "name": name, "protocol": protocol,
        "runtime": runtime, "setup": setup, "source": url,
        "local_runtime_eligible": not cloud_required,
        "verified_no_internet": (
            not cloud_required and physical_interface_verified is True
            and verified_wan_offline is True),
        "strict_local_policy": "blocked" if cloud_required else "eligible_not_verified",
        "caution": (
            "A cloud API is not converted to local merely by wrapping it."
            if cloud_required else
            "Validate exact device firmware, legitimate commissioning credentials, "
            "actual WAN-blocked operation and OEM safety functions."
        ),
        "writes_enabled": False, "commands_issued": 0,
    }

def normalize_heatpump_entities(path_id, *, states, mapping, now,
                                 max_age_seconds=900, allow_cloud=False):
    """Normalize read-only HA sensor snapshots; never infer unmeasured keys."""
    info = plan_local_path(path_id)
    if not allow_cloud and info["runtime"] == "cloud_required":
        raise ValueError("Vendor-cloud device cannot meet strict local-only policy")
    if not isinstance(states, dict) or not isinstance(mapping, dict):
        raise ValueError("states and mapping must be objects")
    if len(states) > 250 or len(mapping) > len(UNIT_MAP):
        raise ValueError("Too many entities")
    now_dt = utc_time(now)
    output = {}
    for metric, entity_id in mapping.items():
        if metric not in UNIT_MAP or not isinstance(entity_id, str):
            raise ValueError("Unknown metric or entity")
        if not entity_id.startswith(("sensor.", "binary_sensor.")):
            raise ValueError("Only sensor and binary_sensor entities accepted")
        row = states.get(entity_id)
        if not isinstance(row, dict):
            output[metric] = {"entity": entity_id, "quality": "missing"}
            continue
        unit = row.get("unit", "boolean" if metric.endswith("_active") else None)
        if unit not in UNIT_MAP[metric]:
            output[metric] = {"entity": entity_id, "quality": "invalid_unit"}
            continue
        try:
            at = utc_time(row["last_updated"])
            age = (now_dt - at).total_seconds()
            if metric.endswith("_active"):
                raw = row.get("state")
                if type(raw) is bool: val = raw
                elif raw in ("on", "off"): val = raw == "on"
                else: raise InvalidMeasurement("Expected explicit on/off")
            else:
                val = number(row.get("state"), metric)
                if unit == "W": val /= 1000
                if unit == "L/h": val /= 1000
                if unit == "L/min": val *= .06
                if metric in ("electric_power_kw", "thermal_power_kw",
                              "water_flow_m3h") and val < 0:
                    raise InvalidMeasurement("Negative power/flow")
            newunit = ("kW" if metric.endswith("_power_kw") else
                       "m³/h" if metric == "water_flow_m3h" else unit)
            output[metric] = {
                "entity": entity_id, "value": val, "unit": newunit,
                "observed_at": iso(at), "age_s": round(age, 1),
                "quality": "clock_skew" if age < -120 else
                           "stale" if age > max_age_seconds else "fresh",
            }
        except (InvalidMeasurement, KeyError, ValueError, TypeError):
            output[metric] = {"entity": entity_id, "quality": "invalid"}
    return {
        "path": path_id, "device": info["name"],
        "measurements": output, "source": "Home Assistant local entity snapshot",
        "commands_issued": 0, "register_writes": 0,
    }
