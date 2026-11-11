"""Site-specific Ouflex reader inside the existing Open HVAC Bridge.

Reuses the independently reviewed Ounet XML/FTP parser delivered in this
repository's Ouflex module. All Modbus traffic here is read-only. No project
firmware, setpoints or raw site XML are published or uploaded.
"""
from __future__ import annotations

import asyncio
import json
import logging

from .const import CONF_HOST, CONF_ALLOW_WRITES
from .profiles import Register, decode
from .transport import ModbusDriver

_LOGGER = logging.getLogger(__name__)

_MAX_BLOCK = 32


class OuflexNativeDriver(ModbusDriver):
    """Automatically load the controller's actual application map on connect."""

    discovery = False
    is_ouflex_native = True

    def __init__(self, hass, data):
        # Do not use ModbusDriver.__init__: that expects a manually pasted JSON
        # profile, which is precisely what this Ouflex automatic mode replaces.
        self.hass = hass
        self.data = {**data, CONF_ALLOW_WRITES: False}
        self.client = None
        self.io_lock = asyncio.Lock()
        self.last_research = []
        self.last_diagnostics = {}
        self.points = []
        self.binary_points = {}
        self.ouflex_doc = None

    async def async_connect(self):
        # This separate module is shipped alongside openlvi in the OpenHVAC
        # development branch. If missing, fail clearly instead of inventing a map.
        from custom_components.ouman_ouflex.ftp_map import fetch_application_map
        from custom_components.ouman_ouflex.pointmap import load_map

        doc = await self.hass.async_add_executor_job(
            fetch_application_map, self.data[CONF_HOST])
        _, native_points = load_map(json.dumps(doc, ensure_ascii=False))
        if not native_points:
            raise ValueError("No documented Ouflex points in XML")
        self.ouflex_doc = doc
        self.points = [
            Register(key=p.key, name=p.name, address=p.address, kind=p.kind,
                     decimals=p.decimals, unit=p.unit, writable=False, area=p.area)
            for p in native_points
        ]
        self.binary_points = {
            p.key: p for p in native_points
            if p.entity in ("binary_sensor", "alarm")
        }
        self.last_diagnostics = {
            "mapped_points": len(self.points),
            "binary_points": len(self.binary_points),
            "source": "read-only local Ounet XML FTP",
            "firmware": doc["identity"]["firmware"],
        }
        await super().async_connect()

    def _batches(self):
        """Contiguous same-area blocks with no undocumented gaps."""
        ordered = sorted(self.points, key=lambda p: (p.area, p.address))
        batches = []
        for point in ordered:
            start = point.address - 1
            stop = start + point.count
            if (batches and batches[-1][0] == point.area
                    and start <= batches[-1][2]
                    and stop - batches[-1][1] <= _MAX_BLOCK):
                batches[-1][2] = max(stop, batches[-1][2])
                batches[-1][3].append(point)
            else:
                batches.append([point.area, start, stop, [point]])
        return batches

    async def _async_read(self):
        if self.client is None or not self.client.connected:
            raise ConnectionError("Ouflex Modbus not connected")
        values = {}
        for area, first, end, points in self._batches():
            try:
                reader = (self.client.read_holding_registers if area == "holding"
                          else self.client.read_input_registers)
                response = await reader(
                    address=first, count=end-first, device_id=self.data["unit_id"])
                if response.isError() or len(response.registers) != end-first:
                    raise ValueError(f"Invalid Ouflex block at {first}")
                for point in points:
                    offset = point.address - 1 - first
                    result = decode(
                        response.registers[offset:offset + point.count], point)
                    if result is not None:
                        values[point.key] = result
            except Exception as err:
                _LOGGER.debug("Ouflex block %s..%s failed: %s", first, end, err)
                # A controller may reject a long block despite accepting single
                # point FC03. Retry only documented points, not unknown addresses.
                for point in points:
                    try:
                        result = await self._read_point(point)
                        if result is not None:
                            values[point.key] = result
                    except Exception as point_err:
                        _LOGGER.debug("Ouflex point %s not readable: %s",
                                      point.key, point_err)
        return values

    async def async_write(self, point, value):
        raise ValueError("Ouflex automatic FTP import is always read-only")
