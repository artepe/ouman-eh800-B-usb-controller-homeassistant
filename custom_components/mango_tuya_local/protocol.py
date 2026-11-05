"""Captured Mango parameter frames. No Home Assistant or cloud dependencies."""

from __future__ import annotations

import base64
import json
import secrets
import struct
from collections import deque
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

FRAME_LENGTH = 244
COMMAND_DP = 117
DESCRIPTION_DPS = {str(n) for n in range(108, 114)}


class MangoError(Exception):
    """An error with a controlled message, never a transport payload."""


class MangoReadError(MangoError):
    """A complete matching parameter reply was not received."""


class MangoProfileError(MangoError):
    """The device does not match the captured parameter profile."""


class MangoValueError(MangoError):
    """A requested value is not an exact permitted raw integer."""


class MangoCancelled(MangoError):
    """A cancelled transaction must restore any possibly delivered write."""


@dataclass(frozen=True)
class Parameter:
    group: int
    slot: int
    identifier: int
    name: str
    section: str
    lower: int
    upper: int
    flags: int
    tag: int
    scale: int = 1
    scale_verified: bool = False
    local_write_evidence: str = "unverified"

    @property
    def key(self) -> str:
        return f"{self.group}:{self.slot}"

    @property
    def id_hex(self) -> str:
        return f"0x{self.identifier:04X}"

    def to_raw(self, value: float) -> int:
        try:
            if isinstance(value, bool):
                raise MangoValueError("not_an_exact_raw_integer")
            scaled = Decimal(str(value)) * self.scale
            if not scaled.is_finite() or scaled != scaled.to_integral_value():
                raise MangoValueError("not_an_exact_raw_integer")
            raw = int(scaled)
        except (InvalidOperation, ValueError, TypeError, OverflowError) as from_error:
            raise MangoValueError("not_an_exact_raw_integer") from from_error
        if not -32768 <= raw <= 32767:
            raise MangoValueError("outside_int16")
        return raw


@dataclass(frozen=True)
class Field:
    slot: int
    identifier: int
    flags: int
    tag: int
    value: int
    upper: int
    lower: int
    placeholder: bool = False

    def validate(self, value: int) -> None:
        if type(value) is not int or not -32768 <= value <= 32767:
            raise MangoValueError("not_int16")
        if not -32768 <= self.lower <= self.upper <= 32767:
            raise MangoValueError("invalid_device_bounds")
        if not self.lower <= value <= self.upper:
            raise MangoValueError("outside_fresh_device_bounds")

    def same_metadata(self, other: Field) -> bool:
        return (self.slot, self.identifier, self.flags, self.tag, self.lower, self.upper) == (
            other.slot,
            other.identifier,
            other.flags,
            other.tag,
            other.lower,
            other.upper,
        )


@dataclass(frozen=True)
class Snapshot:
    group: int
    header_hex: str
    fields: tuple[Field, ...]
    received_at: float

    def field(self, parameter: Parameter) -> Field:
        if self.group != parameter.group or parameter.slot >= len(self.fields):
            raise MangoProfileError("parameter_route_mismatch")
        field = self.fields[parameter.slot]
        if field.identifier != parameter.identifier or field.placeholder:
            raise MangoProfileError("parameter_identifier_mismatch")
        return field


class Profile:
    def __init__(self, data: dict[str, Any]):
        self.sections = {s["group"]: s for s in data["sections"]}
        if len(data["sections"]) != 17 or set(self.sections) != set(range(17)):
            raise MangoProfileError("profile_section_count")
        self.parameters: dict[str, Parameter] = {}
        for section in self.sections.values():
            count, total = section["real_count"], section["declared_count"]
            if (
                not 0 < count <= total <= 255
                or len(section["fields"]) != count
                or len(section["record_ids_in_order"]) != total
                or section["page_count"] != (total + 22) // 23
            ):
                raise MangoProfileError("profile_section_layout")
        for row in data["routes"]:
            p = Parameter(
                row["group"],
                row["slot"],
                int(row["id_hex"], 16),
                row["name"],
                row["section"],
                row["raw_lower"],
                row["raw_upper"],
                row["flags_raw"],
                row["tag_raw"],
                row.get("scale", 1),
                row.get("scale_verified", False),
                row.get("local_write_evidence", "unverified"),
            )
            section = self.sections.get(p.group)
            if section is None or not 0 <= p.slot < section["real_count"] or p.key in self.parameters:
                raise MangoProfileError("profile_duplicate_or_backup_route")
            label = section["fields"][p.slot]
            if (
                label["slot"] != p.slot
                or label["id_hex"] != p.id_hex
                or label["name"] != p.name
                or section["record_ids_in_order"][p.slot] != p.identifier
            ):
                raise MangoProfileError("profile_identifier_order")
            self.parameters[p.key] = p
        s2 = self.sections[16]
        if (
            len(self.parameters) != 770
            or sum(s["real_count"] for s in self.sections.values()) != 770
            or any(s["declared_count"] != s["real_count"] for g, s in self.sections.items() if g != 16)
            or s2["real_count"] != 14
            or s2["declared_count"] != 48
            or s2["record_ids_in_order"][14:] != [0x0890] * 34
        ):
            raise MangoProfileError("profile_770_routes_and_34_backups")
        self.known_select_options = data.get("known_select_options", {})

    @classmethod
    def load(cls) -> Profile:
        return cls(json.loads(Path(__file__).with_name("profile.json").read_text()))

    def parameter(self, group: int, slot: int) -> Parameter:
        if type(group) is not int or type(slot) is not int:
            raise MangoProfileError("parameter_route_mismatch")
        try:
            return self.parameters[f"{group}:{slot}"]
        except KeyError as error:
            raise MangoProfileError("unknown_or_backup_parameter") from error


def read_frame(header: bytes, group: int) -> bytes:
    if not isinstance(header, bytes) or len(header) != 3 or type(group) is not int or group not in range(17):
        raise MangoProfileError("invalid_read_route")
    raw = bytearray(FRAME_LENGTH)
    raw[:8] = b"\x01" + header + bytes((3, 4, 0, group))
    return bytes(raw)


def write_frame(header: bytes, parameter: Parameter, field: Field, value: int) -> bytes:
    if (
        not isinstance(header, bytes)
        or len(header) != 3
        or parameter.group not in range(17)
        or not 0 <= parameter.slot < 48
        or field.slot != parameter.slot
        or field.identifier != parameter.identifier
        or field.placeholder
    ):
        raise MangoProfileError("invalid_write_route")
    field.validate(value)
    raw = bytearray(FRAME_LENGTH)
    raw[:9] = b"\x01" + header + bytes((4, 0, 0, parameter.group, parameter.slot))
    struct.pack_into(">h", raw, 9, value)
    return bytes(raw)


class Headers:
    """Do not reuse any of the 4096 most recent request headers."""

    def __init__(self, factory=secrets.token_bytes):
        self.factory = factory
        self.recent: deque[bytes] = deque()
        self.used: set[bytes] = set()

    def new(self) -> bytes:
        for _ in range(128):
            header = self.factory(3)
            if isinstance(header, bytes) and len(header) == 3 and header not in self.used:
                self.used.add(header)
                self.recent.append(header)
                if len(self.recent) > 4096:
                    self.used.remove(self.recent.popleft())
                return header
        raise MangoError("fresh_header_unavailable")


class Collector:
    def __init__(self, header: bytes, section: dict[str, Any]):
        self.header, self.section = header, section
        self.pages: dict[int, tuple[Field, ...]] = {}
        self.received_at = 0.0

    def record(self, message: Any, received_at: float) -> None:
        if not isinstance(message, dict) or not isinstance(message.get("dps"), dict):
            return
        s = self.section
        for dp, encoded in message["dps"].items():
            if str(dp) not in DESCRIPTION_DPS or not isinstance(encoded, str):
                continue
            try:
                raw = base64.b64decode(encoded, validate=True)
            except ValueError:
                continue
            if (
                len(raw) != FRAME_LENGTH
                or raw[0] != 1
                or raw[1:4] != self.header
                or raw[4] != s["page_count"]
                or raw[5] >= raw[4]
                or raw[6:9] != bytes((5, s["group"], s["declared_count"]))
            ):
                continue
            start = raw[5] * 23
            ids = s["record_ids_in_order"][start : start + 23]
            if any(raw[9 + len(ids) * 10 :]):
                continue
            fields = []
            for index, expected in enumerate(ids):
                ident, flags, tag, value, upper, lower = struct.unpack_from(">HBBhhh", raw, 9 + index * 10)
                if ident != expected:
                    break
                slot = start + index
                fields.append(Field(slot, ident, flags, tag, value, upper, lower, slot >= s["real_count"]))
            if len(fields) == len(ids):
                self.pages[raw[5]] = tuple(fields)
                self.received_at = max(self.received_at, received_at)

    @property
    def complete(self) -> bool:
        return set(self.pages) == set(range(self.section["page_count"]))

    def result(self) -> Snapshot:
        if not self.complete:
            raise MangoReadError("incomplete_matching_description")
        fields = tuple(f for page in range(self.section["page_count"]) for f in self.pages[page])
        return Snapshot(
            self.section["group"], self.header.hex(), fields[: self.section["real_count"]], self.received_at
        )


def common_temperatures(dps: dict[str, Any]) -> dict[str, float]:
    """Only the two observed DP105 fields; never fall back to stale DP16."""
    encoded = dps.get("105")
    if not isinstance(encoded, str):
        return {}
    try:
        raw = base64.b64decode(encoded, validate=True)
    except ValueError:
        return {}
    if len(raw) != FRAME_LENGTH or raw[:6] != bytes.fromhex("010100010001"):
        return {}
    target, upper, lower = struct.unpack_from(">hhh", raw, 14)
    current = struct.unpack_from(">h", raw, 92)[0]
    result = {}
    if -50 <= lower <= target <= upper <= 100:
        result["target_temperature"] = float(target)
    if -500 <= current <= 1200:
        result["current_temperature"] = current / 10
    return result
