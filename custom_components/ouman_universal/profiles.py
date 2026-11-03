"""Documented Modbus register points; physical testing still required.

Addresses are *1-based* in Ouman PDF tables. This module deliberately
does not guess unknown registers, firmware versions or write permissions.
"""
from dataclasses import dataclass
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
    temp("outdoor", "Ulkolämpötila", 201),
    temp("l1_supply", "L1 menovesi", 202),
    temp("l1_return", "L1 paluuvesi", 203),
    temp("l2_supply", "L2 menovesi", 205),
    temp("dhw_supply", "Käyttöveden menovesi", 208),
    temp("dhw_return", "Käyttöveden kierto", 209),
]
PROFILE_MAPS = {
    "A203": BASE + [
        Register("l1_room_target", "L1 huoneasetus", 818, "s16", 1, "°C", 5, 50, True),
        Register("l2_room_target", "L2 huoneasetus", 905, "s16", 1, "°C", 5, 50, True),
    ],
    "S203": BASE + [
        Register("l1_room_target", "L1 huoneasetus", 793, "s16", 1, "°C", 5, 50, True),
        Register("l2_room_target", "L2 huoneasetus", 713, "s16", 1, "°C", 5, 50, True),
    ],
    "C203": BASE,
    "H23": BASE,
}
SUPPORTED_TYPES = frozenset(("s16", "u16", "s32", "u32"))

def parse_profile(raw: str) -> list[Register]:
    """Parse operator-supplied, explicitly *read-only* point list.

    Example {"registers":[{"key":"room","name":"Huone","address":305,
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
        if type(address) is not int or not 1 <= address <= 65535:
            raise ValueError("Invalid 1-based address")
        if type(decimals) is not int or not 0 <= decimals <= 5:
            raise ValueError("Decimals must be between 0 and 5")
        keys.add(key)
        # Never honor "writable":true from untrusted or user-supplied templates.
        points.append(Register(key, name, address, kind, decimals, item.get("unit"), writable=False))
    return points

def profile_for(model: str, firmware: str, profile_json: str) -> list[Register]:
    if profile_json.strip():
        return parse_profile(profile_json)
    if model not in PROFILE_MAPS:
        raise ValueError("This model requires a site-specific read-only JSON register profile")
    if firmware.strip() != VERSIONS[model]:
        raise ValueError("Firmware must match the documented register map, or supply a custom profile")
    return list(PROFILE_MAPS[model])

def decode(registers: list[int], point: Register) -> float:
    """Ouman uses high-word-first, big-endian signed/unsigned register data."""
    if len(registers) != point.count:
        raise ValueError("Missing Modbus register")
    raw = (registers[0] << 16 | registers[1]) if point.count == 2 else registers[0]
    bits = 32 if point.count == 2 else 16
    if point.kind.startswith("s") and raw & (1 << (bits - 1)):
        raw -= 1 << bits
    return raw / (10 ** point.decimals)

def encode(value: float, point: Register) -> list[int]:
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
