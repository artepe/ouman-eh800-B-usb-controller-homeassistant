"""Pure unit helpers: normalise vendor unit spellings, pick HA sensor classes.

No Home Assistant imports, so the mapping can be unit tested offline.

Only *unambiguous* units get a device class. A supply/return difference in
kelvin ("K") is a temperature *difference*, never an absolute temperature
(as an absolute value HA would show 5 K as -268 °C). Percent, ppm and rpm
stay without a device class because the same unit is used for valve
positions, thresholds and humidity alike.
"""
from __future__ import annotations

# Exact library/vendor spellings -> Home Assistant unit strings.
# pyMeterBus reports e.g. "C", "m^3" and "m^3/h" for EN 13757 records.
# Matching is case-sensitive on purpose: "mW" and "MW" differ by 10^9.
_ALIASES = {
    "C": "°C", "°c": "°C", "degC": "°C", "deg C": "°C", "Celsius": "°C",
    "F": "°F", "°f": "°F", "degF": "°F", "Fahrenheit": "°F",
    "m^3": "m³", "m3": "m³",
    "m^3/h": "m³/h", "m3/h": "m³/h",
    "m^3/min": "m³/min", "m^3/s": "m³/s",
    "kwh": "kWh", "KWH": "kWh", "kw": "kW", "KW": "kW",
}

# Units that only ever describe a non-numeric value (M-Bus date records).
_NON_NUMERIC = frozenset(("date", "time", "date time", "datetime"))

_TEMPERATURE = frozenset(("°C", "°F"))
_TEMPERATURE_DELTA = frozenset(("K",))
_ENERGY = frozenset(("J", "kJ", "MJ", "GJ", "Wh", "kWh", "MWh"))
_POWER = frozenset(("W", "kW", "MW"))
_VOLUME = frozenset(("m³", "L"))
_VOLUME_FLOW = frozenset(("m³/h", "m³/min", "m³/s", "L/h", "L/min", "L/s"))
_PRESSURE = frozenset(("Pa", "kPa", "bar", "mbar"))


def normalize_unit(unit: object) -> str | None:
    """Return a Home Assistant unit string, or None for no/non-numeric unit."""
    if unit is None:
        return None
    text = str(unit).strip()
    if not text or text.lower() == "none" or text.lower() in _NON_NUMERIC:
        return None
    return _ALIASES.get(text, text)


def sensor_classes(unit: str | None) -> tuple[str | None, str | None]:
    """Return (device_class, state_class) values for a point's unit.

    Values are the HA enum *values* (e.g. "temperature", "measurement") so
    this module stays importable without Home Assistant. Unit-less points
    are status codes or enumerations and get no state class. Energy and
    volume are meter totals (total_increasing), everything else is an
    instantaneous measurement.
    """
    if unit is None:
        return None, None
    if unit in _TEMPERATURE:
        return "temperature", "measurement"
    if unit in _TEMPERATURE_DELTA:
        return "temperature_delta", "measurement"
    if unit in _ENERGY:
        return "energy", "total_increasing"
    if unit in _VOLUME:
        return "volume", "total_increasing"
    if unit in _POWER:
        return "power", "measurement"
    if unit in _VOLUME_FLOW:
        return "volume_flow_rate", "measurement"
    if unit in _PRESSURE:
        return "pressure", "measurement"
    return None, "measurement"
