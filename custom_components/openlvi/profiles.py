"""Documented Modbus register points; physical testing still required.

Addresses are *1-based* in Ouman PDF tables. This module deliberately
does not guess unknown registers, firmware versions or write permissions.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
import json

@dataclass(frozen=True)
class Register:
    key: str
    name: str
    address: int
    kind: str = "s16"
    decimals: int = 1
    unit: str | None = "°C"
    minimum: float | None = None
    maximum: float | None = None
    writable: bool = False
    area: str = "holding"  # holding (FC03) or input (FC04)
    offset: float = 0.0  # Read-only engineering-unit correction, e.g. centikelvin
    invalid_raw_values: tuple[int, ...] = ()  # Explicit 16-bit no-data markers

    @property
    def count(self):
        return 2 if self.kind in ("s32", "u32") else 1

def temp(key: str, name: str, address: int) -> Register:
    return Register(key, name, address)

# Verified model + firmware register tables from Ouman documentation.
# These are conservative *subsets* of the PDF, not full point databases.
VERSIONS = {"A203": "2.0.2", "S203": "3.0.10", "C203": "3.0.10", "H23": "4.0.5"}
SOURCES = {
    "A203": "https://ouflextool.ouman.net/downloads/DeviceTemplates/Ouman/A203/v202/A203_2.0.2_Modbus_fi-FI.pdf",
    "S203": "https://ouflextool.ouman.net/downloads/DeviceTemplates/Ouman/S203/v3010/S203%2016MBModbus_FI.pdf",
    "C203": "https://ouflextool.ouman.net/downloads/DeviceTemplates/Ouman/C203/v3010/C203_3.0.10_Modbus_fi.pdf",
    "H23": "https://ouflextool.ouman.net/downloads/DeviceTemplates/Ouman/H23/v405/H23%204.0.5_Modbus_fi.pdf",
}
BASE = [
    temp("outdoor", "Outdoor temperature", 201),
    temp("l1_supply", "L1 supply water temperature", 202),
    temp("l1_return", "L1 return water temperature", 203),
    temp("l2_supply", "L2 supply water temperature", 205),
    temp("dhw_supply", "Domestic hot water supply", 208),
    temp("dhw_return", "Domestic hot water recirculation", 209),
]
PROFILE_MAPS = {
    "A203": BASE + [
        Register("l1_room_target", "L1 room temperature setpoint", 818, "s16", 1, "°C", 5, 50, True),
        Register("l2_room_target", "L2 room temperature setpoint", 905, "s16", 1, "°C", 5, 50, True),
    ],
    "S203": BASE + [
        Register("l1_room_target", "L1 room temperature setpoint", 793, "s16", 1, "°C", 5, 50, True),
        Register("l2_room_target", "L2 room temperature setpoint", 713, "s16", 1, "°C", 5, 50, True),
    ],
    "C203": BASE + [
        Register("l1_room_target", "L1 room temperature setpoint", 585, "s16", 1, "°C", 5, 50, True),
        Register("l2_room_target", "L2 room temperature setpoint", 751, "s16", 1, "°C", 5, 50, True),
    ],
    "H23": BASE + [
        Register("l1_room_target", "L1 room temperature setpoint", 432, "s16", 1, "°C", 5, 35, True),
        Register("l2_room_target", "L2 room temperature setpoint", 453, "s16", 1, "°C", 5, 35, True),
    ],
}
SUPPORTED_TYPES = frozenset(("s16", "u16", "s32", "u32"))

def parse_profile(raw: str) -> list[Register]:
    """Parse operator-supplied, explicitly *read-only* point list.

    Example {"registers":[{"key":"room","name":"Room","address":305,
      "kind":"s32","decimals":1,"unit":"°C"}]}.
    """
    doc = json.loads(raw)
    if not isinstance(doc, dict) or not isinstance(doc.get("registers"), list):
        raise ValueError('Expected JSON object with "registers" array')
    entries = doc["registers"]
    if not 1 <= len(entries) <= 128:
        raise ValueError("Register count must be 1-128")
    points = []
    keys = set()
    for item in entries:
        if not isinstance(item, dict):
            raise ValueError("Each register must be a JSON object")
        key, name = item["key"], item["name"]
        address = item["address"]
        kind = item.get("kind", "s16").lower()
        decimals = item.get("decimals", 0)
        if not isinstance(key, str) or not key.isidentifier() or len(key) > 64:
            raise ValueError("Invalid register key")
        if not isinstance(name, str) or not (1 <= len(name) <= 90):
            raise ValueError("Invalid register name")
        if key in keys or kind not in SUPPORTED_TYPES:
            raise ValueError("Duplicate key or unsupported register type")
        if type(address) is not int or not 1 <= address <= 65536:
            raise ValueError("Invalid 1-based address")
        if address - 1 + (2 if kind in ("s32", "u32") else 1) > 65536:
            raise ValueError("Register extends past Modbus address space")
        if type(decimals) is not int or not 0 <= decimals <= 5:
            raise ValueError("Decimals must be between 0 and 5")
        offset = item.get("offset", 0)
        if type(offset) not in (int, float) or not isfinite(offset) or abs(offset) > 1000:
            raise ValueError("Register offset must be a finite number within +/-1000")
        invalid_raw_values = item.get("invalid_raw_values", [])
        if (not isinstance(invalid_raw_values, list)
                or len(invalid_raw_values) > 8
                or any(type(v) is not int or v < 0 or v > 65535
                       for v in invalid_raw_values)
                or len(set(invalid_raw_values)) != len(invalid_raw_values)
                or (invalid_raw_values and kind in ("s32", "u32"))):
            raise ValueError("Invalid 16-bit no-data markers")
        keys.add(key)
        # Never honor "writable":true from untrusted or user-supplied templates.
        area = item.get("area", "holding")
        if area not in ("holding", "input"):
            raise ValueError("Use holding or input register area")
        points.append(Register(key, name, address, kind, decimals, item.get("unit"), writable=False, area=area, offset=float(offset),
                               invalid_raw_values=tuple(invalid_raw_values)))
    return points

def profile_for(model: str, firmware: str, profile_json: str) -> list[Register]:
    if profile_json.strip():
        return parse_profile(profile_json)
    if model not in PROFILE_MAPS:
        raise ValueError("This model requires a site-specific read-only JSON register profile")
    if firmware.strip() != VERSIONS[model]:
        raise ValueError("Firmware must match the documented register map, or supply a custom profile")
    return list(PROFILE_MAPS[model])

def decode(registers: list[int], point: Register) -> float | None:
    """Ouman uses high-word-first, big-endian signed/unsigned register data."""
    if len(registers) != point.count:
        raise ValueError("Missing Modbus register")
    if point.count == 1 and registers[0] in point.invalid_raw_values:
        return None
    raw = (registers[0] << 16 | registers[1]) if point.count == 2 else registers[0]
    bits = 32 if point.count == 2 else 16
    if point.kind.startswith("s") and raw & (1 << (bits - 1)):
        raw -= 1 << bits
    return raw / (10 ** point.decimals) + point.offset

def encode(value: float, point: Register) -> list[int]:
    if point.offset or point.invalid_raw_values:
        raise ValueError("Offset and no-data marker points are read-only")
    if not point.writable or point.minimum is None or point.maximum is None:
        raise ValueError("This point is not in the verified write allowlist")
    if not point.minimum <= value <= point.maximum:
        raise ValueError("Setpoint is outside documented bounds")
    scaled = int(round(value * 10 ** point.decimals))
    if abs(scaled / (10 ** point.decimals) - value) > 0.00001:
        raise ValueError("Setpoint precision is unsupported")
    bits = 32 if point.count == 2 else 16
    lower, upper = (-(1 << (bits - 1)), (1 << (bits - 1)) - 1) if point.kind.startswith("s") else (0, (1 << bits) - 1)
    if not lower <= scaled <= upper:
        raise ValueError("Setpoint overflows its register")
    raw = scaled & ((1 << bits) - 1)
    return [(raw >> 16) & 0xffff, raw & 0xffff] if bits == 32 else [raw]


# OpenLVI Bridge: multi-vendor point maps (all addresses are vendor 1-based).
# Danfoss ECL examples: A266.1 application; PNU 10202 is sensor S2 (scale 100).
DANFOSS_MODELS = ("ECL Comfort 210", "ECL Comfort 296", "ECL Comfort 310", "ECL Comfort 310B")
DANFOSS_PNU_SOURCE = "https://assets.danfoss.com/documents/198690/AQ074886472234en-010601.pdf"
SWEGON_SOURCE = "https://www.swegon.com/globalassets/digizuite/18172-en-casa_modbusregisters_en.pdf"
REGIN_SOURCE = "https://www.regincontrols.com/globalassets/pimmediafiles/documents/corrigo_e_ventilation_variables_for_exoline_and_modbus_3.2_manu_en.pdf"

# Swegon CASA Genius: SEM/SEC connection, software 4.x, vendor SCB4.3 list.
# 3x = input, 4x = holding. Emergency stop deliberately excluded.
SWEGON_GENIUS = [
    Register("operation_mode", "Operation mode (1 Away, 2 Home, 3 Boost)", 5001, "u16", 0, None, 1, 3, True, "holding"),
    Register("co2_auto", "CO2 automation", 5009, "u16", 0, None, area="holding"),
    Register("co2_home_limit", "CO2 home threshold", 5114, "u16", 0, "ppm", area="holding"),
    Register("co2_away_limit", "CO2 away threshold", 5115, "u16", 0, "ppm", area="holding"),
    Register("unit_state", "Ventilation unit status", 6301, "u16", 0, None, area="input"),
    Register("supply_fan_percent", "Supply fan control", 6303, "u16", 0, "%", area="input"),
    Register("extract_fan_percent", "Extract fan control", 6304, "u16", 0, "%", area="input"),
    Register("supply_fan_rpm", "Supply fan RPM", 6305, "u16", 0, "rpm", area="input"),
    Register("extract_fan_rpm", "Extract fan RPM", 6306, "u16", 0, "rpm", area="input"),
    Register("supply_temp_target", "Supply air temperature target", 6320, "s16", 1, "°C", area="input"),
    Register("heating_state", "Heating and heat recovery status", 6370, "u16", 0, None, area="input"),
    Register("exchanger_bypass", "Heat exchanger bypass damper", 6348, "u16", 0, "%", area="input"),
]
# Regin Corrigo E ventilation, software 3.2 (real signals scaled /10).
REGIN_CORRIGO_E = [
    Register("outdoor_temp", "Outdoor temperature", 1, "s16", 1, "°C", area="input"),
    Register("unit_mode", "Operating state", 3, "u16", 0, None, area="input"),
    Register("supply_temp", "Supply air", 7, "s16", 1, "°C", area="input"),
    Register("supply_target", "Supply target", 8, "s16", 1, "°C", area="input"),
    Register("extract_temp", "Extract air", 9, "s16", 1, "°C", area="input"),
    Register("supply_flow", "Supply air flow", 15, "u16", 0, "m³/h", area="input"),
    Register("extract_flow", "Extract air flow", 16, "u16", 0, "m³/h", area="input"),
]


# Additional source-backed, READ-ONLY point maps. These require the exact
# hardware/firmware and a physical acceptance test before production use.
# NEVER assume that other floor heating generations share these registers.
UPONOR_X148_INPUTS = [
    # The manufacturer's 30001 notation maps to zero-based FC04 address 0.
    # Generic OpenLVI profiles store one-based PDU addresses, not 3xxxx tags.
    Register("controller_outdoor_temp", "Controller outdoor temperature", 1,
             "s16", 1, "°C", area="input", invalid_raw_values=(0x7fff,)),
]
UPONOR_X148_INPUTS += [
    Register(f"room_{i}_temperature", f"Room {i} temperature", i + 1,
             "s16", 1, "°C", area="input", invalid_raw_values=(0x7fff,))
    for i in range(1, 13)
]
UPONOR_X148_INPUTS += [
    Register(f"room_{i}_humidity", f"Room {i} humidity", i + 13,
             "u16", 0, "%", area="input", invalid_raw_values=(0x7fff,))
    for i in range(1, 13)
]
# Manufacturer Roth Touchline SL Modbus register table: R and R/W points
# are all imported as non-writable sensors; only a first-zone subset is
# enabled until channel allocation / firmware are physically confirmed.
ROTH_TOUCHLINE_SL = [
    Register("fw_major", "Firmware major version", 3, "u16", 0, None),
    Register("fw_minor", "Firmware minor version", 4, "u16", 0, None),
    Register("fw_revision", "Firmware revision", 5, "u16", 0, None),
    Register("zone_1_temperature", "Zone 1 room temperature", 23, "u16", 1, "°C"),
    Register("zone_1_floor_temperature", "Zone 1 floor temperature", 74, "u16", 1, "°C"),
    Register("zone_1_humidity", "Zone 1 humidity", 122, "u16", 1, "%"),
    Register("zone_1_actuator_open", "Zone 1 actuator opening", 170, "u16", 0, "%"),
    Register("zone_1_target", "Zone 1 temperature target", 221, "u16", 1, "°C"),
    Register("zone_1_battery", "Zone 1 battery", 270, "u16", 0, "%"),
]
# Tosibox official page lists offsets relative to holding 40001. This driver
# uses one-based PDU addresses. Offset 14 is address 15 in this representation.
# READ-ONLY. Registers for changing WAN/VPN access or sending SMS are excluded.
TOSIBOX_STATUS_BASE = [
    Register("cellular_rsrp_raw", "Cellular RSRP raw", 15, "u16", 0, None,
             invalid_raw_values=(0xffff,)),
    Register("cellular_rssi_raw", "Cellular RSSI raw", 16, "u16", 0, None,
             invalid_raw_values=(0xffff,)),
    Register("internet_interface", "Active Internet interface code", 17,
             "u16", 0, None, invalid_raw_values=(0xffff,)),
    Register("tosibox_cloud_ok", "Tosibox cloud connection (0/1)", 18,
             "u16", 0, None, invalid_raw_values=(0xffff,)),
    Register("vpn_tunnel_count", "VPN tunnel count", 19,
             "u16", 0, None, invalid_raw_values=(0xffff,)),
    Register("internet_enabled", "Internet access enabled (read-only)", 20,
             "u16", 0, None, invalid_raw_values=(0xffff,)),
    Register("vpn_enabled", "VPN access enabled (read-only)", 21,
             "u16", 0, None, invalid_raw_values=(0xffff,)),
]
TOSIBOX_FIRMWARE = [
    Register("firmware_major", "Tosibox firmware major", 22,
             "u16", 0, None, invalid_raw_values=(0xffff,)),
    Register("firmware_minor", "Tosibox firmware minor", 23,
             "u16", 0, None, invalid_raw_values=(0xffff,)),
    Register("firmware_patch", "Tosibox firmware patch", 24,
             "u16", 0, None, invalid_raw_values=(0xffff,)),
]


def tosibox_firmware_tuple(value: str) -> tuple[int, int, int]:
    """Require an explicit firmware string; no guessing from model names."""
    import re
    if not re.fullmatch(r"\d{1,3}\.\d{1,3}\.\d{1,3}", value.strip()):
        raise ValueError("Tosibox firmware must be supplied as major.minor.patch")
    return tuple(int(i) for i in value.split("."))



_ouman_profile_for = profile_for

def profile_for(model: str, firmware: str, profile_json: str, application_key: str = "", *, discovery_mode: bool = False) -> list[Register]:
    """Select only matching vendor registers; discovery has no inferred points."""
    if discovery_mode:
        return []
    if profile_json.strip():
        return parse_profile(profile_json)
    if model in PROFILE_MAPS:
        return _ouman_profile_for(model, firmware, "")
    if model == "Smatrix Base PRO X-148":
        return list(UPONOR_X148_INPUTS)
    if model == "Touchline SL Modbus":
        return list(ROTH_TOUCHLINE_SL)
    if model.startswith("TOSIBOX "):
        version = tosibox_firmware_tuple(firmware)
        if version < (5, 5, 0):
            raise ValueError("Tosibox Modbus status needs firmware >= 5.5.0")
        points = list(TOSIBOX_STATUS_BASE)
        if version >= (5, 6, 0):
            points.extend(TOSIBOX_FIRMWARE)
        return points
    if model in DANFOSS_MODELS:
        # Globally documented PNU read; application-specific points enabled
        # only after exact installed application key is entered by operator.
        points = [Register("sensor_s2", "Sensor S2", 10202, "s16", 2, "°C")]
        if application_key.strip().upper() == "A266.1":
            points.append(Register("comfort_target", "Circuit 1 comfort temperature", 11180,
                                   "s16", 1, "°C"))
        return points
    if model == "CASA Genius":
        if not firmware.strip().startswith("4."):
            raise ValueError("CASA Genius requires confirmed 4.x firmware and SEM/SEC")
        return list(SWEGON_GENIUS)
    if model == "Corrigo E Ventilation":
        if not firmware.strip().startswith("3.2"):
            raise ValueError("Corrigo E ventilation requires confirmed 3.2 firmware")
        return list(REGIN_CORRIGO_E)
    raise ValueError("This controller requires an exact read-only JSON Modbus register map")

