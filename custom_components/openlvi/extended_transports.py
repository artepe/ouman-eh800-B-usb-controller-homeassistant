"""Read-only BACnet/IP and wired M-Bus adapters for OpenLVI.

BACnet enumerates *only the selected device* (up to 32 objects). It never
broadcasts Who-Is or writes property values. Wired M-Bus needs an active
M-Bus master/converter, NOT a passive RS-485/TTL USB dongle.
"""
from __future__ import annotations

import asyncio
from decimal import Decimal
import ipaddress
import json
import logging
from math import isfinite
import re

from .profiles import Register
from .units import normalize_unit

_LOGGER = logging.getLogger(__name__)
BACNET_TYPES = frozenset((
    "analog-input", "analog-value", "analog-output",
    "binary-input", "binary-value", "binary-output",
    "multi-state-input", "multi-state-value", "multi-state-output",
))
KEY_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


def parse_bacnet_objects(raw: str) -> list[dict]:
    """Validate an operator-provided, non-writable BACnet point list."""
    profile = json.loads(raw)
    if not isinstance(profile, dict) or not isinstance(profile.get("objects"), list):
        raise ValueError('BACnet profile must contain an "objects" array')
    items = profile["objects"]
    if not 1 <= len(items) <= 64:
        raise ValueError("BACnet point count must be 1..64")
    keys = set()
    result = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Invalid BACnet point")
        key = item.get("key")
        typ = item.get("type")
        instance = item.get("instance")
        if not isinstance(key, str) or not KEY_RE.fullmatch(key) or key in keys:
            raise ValueError("Invalid or duplicate BACnet point key")
        if typ not in BACNET_TYPES:
            raise ValueError("Unsupported BACnet object type")
        if type(instance) is not int or not (0 <= instance <= 4194302):
            raise ValueError("Invalid BACnet object instance")
        name = item.get("name", key)
        unit = item.get("unit")
        if not isinstance(name, str) or len(name) > 100:
            raise ValueError("Invalid BACnet name")
        if unit is not None and (not isinstance(unit, str) or len(unit) > 16):
            raise ValueError("Invalid BACnet unit")
        keys.add(key)
        result.append({"key": key, "type": typ, "instance": instance,
                       "name": name, "unit": unit})
    return result


def bacnet_bind_args(local_address: str, local_instance: int):
    """Build the BACpypes3 minimal local client application objects.

    Device object is local-only client identity. BACnet remote writes are
    deliberately unsupported regardless of settings.
    """
    from bacpypes3.local.networkport import NetworkPortObject
    from bacpypes3.object import DeviceObject

    local_device = DeviceObject(
        objectIdentifier=("device", local_instance),
        objectName="OpenLVI-Bridge-Reader",
        vendorIdentifier=0,
    )
    network_port = NetworkPortObject(
        local_address,
        objectIdentifier=("network-port", 1),
        objectName="OpenLVI-BACnet-Port",
        networkNumber=None,
        networkNumberQuality="unknown",
    )
    return [local_device, network_port]


class BacnetDriver:
    def __init__(self, hass, data):
        self.data = data
        self.hass = hass
        self.app = None
        self.points: list[Register] = []
        self.objects: dict[str, str] = {}
        raw = data.get("profile_json", "").strip()
        self._configured = parse_bacnet_objects(raw) if raw else []
        self.host = data["host"]
        self.device_instance = data["bacnet_device_id"]
        self.local_address = data["bacnet_local_address"]
        self.local_instance = data["bacnet_local_instance"]
        # BACnet/IP uses UDP 47808 by default, no arbitrary internet targets.
        remote_ip = ipaddress.ip_address(self.host)
        bind_ip = ipaddress.ip_interface(self.local_address).ip
        if not remote_ip.is_private or not bind_ip.is_private:
            raise ValueError("BACnet/IP endpoints must be on private networks")
        if self.device_instance == self.local_instance:
            raise ValueError("Local and remote BACnet device IDs must differ")

    def _add_point(self, entry: dict):
        self.objects[entry["key"]] = f'{entry["type"]},{entry["instance"]}'
        self.points.append(Register(
            key=entry["key"], name=entry["name"], address=0,
            kind="s16", decimals=0, unit=entry.get("unit"), writable=False,
        ))

    async def async_connect(self):
        from bacpypes3.app import Application
        self.app = Application.from_object_list(
            bacnet_bind_args(self.local_address, self.local_instance)
        )
        if self._configured:
            for item in self._configured:
                self._add_point(item)

    async def _discover_selected_device(self):
        """Bounded, targeted object-list enumeration; no network broadcast."""
        if self.app is None:
            raise ConnectionError("BACnet not connected")
        count = await asyncio.wait_for(
            self.app.read_property(self.host, f"device,{self.device_instance}",
                                   "object-list[0]"), timeout=8
        )
        if not 0 < int(count) <= 50000:
            raise ValueError("Invalid BACnet object-list length")
        for n in range(1, min(int(count), 32) + 1):
            try:
                obj = await asyncio.wait_for(
                    self.app.read_property(self.host, f"device,{self.device_instance}",
                                           f"object-list[{n}]"), timeout=6
                )
                typ, instance = str(obj[0]).replace("_", "-"), int(obj[1])
                if typ not in BACNET_TYPES:
                    continue
                identifier = f"{typ},{instance}"
                name = str(await asyncio.wait_for(
                    self.app.read_property(self.host, identifier, "object-name"),
                    timeout=6
                ))
                key = f'{typ.replace("-", "_")}_{instance}'
                self._add_point({"key": key, "name": name[:100],
                                 "type": typ, "instance": instance, "unit": None})
            except Exception as err:
                _LOGGER.debug("Skipping BACnet object %s: %s", n, err)
        if not self.points:
            raise ValueError("No readable BACnet objects found on this device")

    async def async_read(self):
        if self.app is None:
            raise ConnectionError("BACnet disconnected")
        if not self.points:
            await self._discover_selected_device()
        values = {}
        for point in self.points:
            try:
                value = await asyncio.wait_for(
                    self.app.read_property(self.host, self.objects[point.key],
                                           "present-value"), timeout=6
                )
                if hasattr(value, "get_value"):
                    value = value.get_value()
                if isinstance(value, (float, int, Decimal)):
                    value = float(value)
                else:
                    value = str(value)
                values[point.key] = value
            except Exception as err:
                _LOGGER.debug("BACnet point %s unreadable: %s", point.key, err)
        return values

    async def async_write(self, point, value):
        raise ValueError("BACnet write support is deliberately disabled")

    async def async_close(self):
        if self.app:
            self.app.close()
            self.app = None


def mbus_records_to_values(records) -> tuple[list[Register], dict]:
    """Decode only present records; no guessed Kamstrup indexes or units.

    pyMeterBus reports units such as "C", "m^3" and "date time"; they are
    normalised to Home Assistant spellings. A record whose value is not a
    number (meter date/time) gets no unit: HA rejects a non-numeric state
    on a sensor that has a unit of measurement.
    """
    points, values = [], {}
    for i, record in enumerate(records[:64], start=1):
        value = getattr(record, "value", None)
        if value is None:
            value = getattr(record, "parsed_value", None)
        if value is None:
            continue
        unit = normalize_unit(getattr(record, "unit", None))
        key = f"record_{i}"
        if isinstance(value, bool):
            value = str(value)
        elif isinstance(value, (int, float, Decimal)):
            value = float(value)
        else:
            try:
                value = float(str(value))
            except (TypeError, ValueError):
                value = str(value)
        if isinstance(value, float) and not isfinite(value):
            continue
        if isinstance(value, str):
            unit = None
        # Do not assign energy/power categories based on index: record layouts
        # depend on the Kamstrup meter's configured M-Bus telegram profile.
        label = f"M-Bus record {i} ({unit})" if unit else f"M-Bus record {i}"
        points.append(Register(key, label, i, "s16", 0, unit, writable=False))
        values[key] = value
    return points, values


class MbusDriver:
    """Wired EN13757 serial M-Bus on an active USB M-Bus master."""
    def __init__(self, hass, data):
        self.hass = hass
        self.data = data
        self.points: list[Register] = []
        self.address = data["unit_id"]
        if not 1 <= self.address <= 250:
            raise ValueError("M-Bus primary address must be 1..250")
        self.port = data["port"]
        self.baudrate = data["baudrate"]

    async def async_connect(self):
        # First passive setup; read request happens during coordinator refresh.
        return

    def _read_sync(self):
        import serial
        import meterbus
        with serial.serial_for_url(
            self.port, baudrate=self.baudrate, bytesize=8, parity="E",
            stopbits=1, timeout=2.0
        ) as conn:
            meterbus.send_ping_frame(conn, self.address)
            ack = meterbus.load(meterbus.recv_frame(conn, 1))
            if not isinstance(ack, meterbus.TelegramACK):
                raise ConnectionError("M-Bus meter did not acknowledge")
            meterbus.send_request_frame(conn, self.address)
            frame = meterbus.load(
                meterbus.recv_frame(conn, meterbus.FRAME_DATA_LENGTH)
            )
            if not isinstance(frame, meterbus.TelegramLong):
                raise ValueError("M-Bus did not return a long data telegram")
            return mbus_records_to_values(frame.records)

    async def async_read(self):
        points, values = await self.hass.async_add_executor_job(self._read_sync)
        if not self.points:
            self.points = points
        return values

    async def async_write(self, point, value):
        raise ValueError("Wired M-Bus is read-only")

    async def async_close(self):
        return
