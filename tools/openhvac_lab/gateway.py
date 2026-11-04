"""Unify already-decoded readings from different transport collectors.

LoRaWAN/OMS/Zigbee/Z-Wave/Matter/BLE decoding is delegated to their
appropriate native radios and verified gateway codecs. Raw payloads
and unsafe source-supplied instructions are deliberately ignored.
"""
from __future__ import annotations
from .core import iso, number, utc_time

SOURCES = frozenset({
    "modbus", "bacnet", "mbus", "wireless_mbus", "lorawan",
    "zigbee", "zwave", "ble", "matter", "knx", "mqtt", "ha_entity",
    "enocean", "ebus", "ems", "dali",
})
UNITS = frozenset({
    "°C", "K", "%", "ppm", "Pa", "bar", "kPa", "W", "kW", "Wh",
    "kWh", "m³/h", "L/min", "rpm", "V", "A", "Hz", "kg/s", "kJ/kg",
    "dBm", "boolean", "count", "none",
})


def normalize_reading(reading, *, now, max_age_seconds=900):
    if not isinstance(reading, dict):
        raise ValueError("Reading must be a JSON object")
    source = reading.get("source")
    if source not in SOURCES:
        raise ValueError("A known transport name is required")
    device = reading.get("device_id")
    point = reading.get("point_key")
    for field, value in (("device_id", device), ("point_key", point)):
        if not isinstance(value, str) or not 1 <= len(value) <= 128:
            raise ValueError(f"Invalid {field}")
    unit = reading.get("unit", "none")
    if unit not in UNITS:
        raise ValueError("Unsupported measurement unit")
    val = reading.get("value")
    if unit == "boolean":
        if not isinstance(val, bool):
            raise ValueError("Boolean state required")
    else:
        val = number(val, "reading value")
    stamp = utc_time(reading.get("observed_at"))
    reference = utc_time(now)
    age = (reference - stamp).total_seconds()
    if age < -120:
        quality = "clock_skew"
    elif age > max_age_seconds:
        quality = "stale"
    else:
        quality = "fresh"
    if reading.get("verified") is not True:
        quality = "unverified" if quality == "fresh" else quality
    return {
        "source": source,
        "device_id": device, "point_key": point,
        "value": val, "unit": unit,
        "observed_at": iso(stamp),
        "age_seconds": round(age, 1),
        "quality": quality,
        "verified": reading.get("verified") is True,
        "read_only": True,
    }


def normalize_bundle(readings, *, now, max_age_seconds=900):
    if not isinstance(readings, list) or len(readings) > 1024:
        raise ValueError("Expected <=1024 readings")
    return {
        "measurements": [
            normalize_reading(row, now=now, max_age_seconds=max_age_seconds)
            for row in readings
        ],
        "radio_gateways_controlled": 0,
        "commands_issued": 0,
    }
