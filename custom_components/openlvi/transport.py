"""Local HTTP, USB and Modbus drivers. No writes occur during discovery."""
from __future__ import annotations
import logging
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_MODEL, CONF_TRANSPORT, CONF_HOST, CONF_PORT, CONF_BAUDRATE,
    CONF_UNIT_ID, CONF_FIRMWARE, CONF_PROFILE, CONF_ALLOW_WRITES,
    CONF_URL, CONF_USERNAME, CONF_PASSWORD, CONF_APPLICATION, CONF_PARITY,
)
from .profiles import Register, profile_for, decode, encode

_LOGGER = logging.getLogger(__name__)

class ModbusDriver:
    def __init__(self, data):
        self.data = data
        self.points = profile_for(
            data[CONF_MODEL], data.get(CONF_FIRMWARE, ""), data.get(CONF_PROFILE, ""), data.get(CONF_APPLICATION, "")
        )
        self.client = None

    async def async_connect(self):
        from pymodbus.client import AsyncModbusTcpClient, AsyncModbusSerialClient
        if self.data[CONF_TRANSPORT] == "modbus_tcp":
            self.client = AsyncModbusTcpClient(
                self.data[CONF_HOST], port=self.data[CONF_PORT], timeout=4, retries=1
            )
        else:
            self.client = AsyncModbusSerialClient(
                port=self.data[CONF_PORT], baudrate=self.data[CONF_BAUDRATE],
                parity=self.data.get(CONF_PARITY, "N"), stopbits=1, bytesize=8, timeout=4, retries=1
            )
        await self.client.connect()
        if not self.client.connected:
            raise ConnectionError("Modbus connection failed")

    async def _read_point(self, point: Register):
        if self.client is None or not self.client.connected:
            raise ConnectionError("Modbus disconnected")
        # Ouman PDFs use 1-based address notation, pymodbus uses 0-based.
        reader = (self.client.read_input_registers if point.area == "input"
                  else self.client.read_holding_registers)
        result = await reader(
            address=point.address - 1, count=point.count,
            device_id=self.data[CONF_UNIT_ID],
        )
        if result.isError() or len(result.registers) != point.count:
            raise ValueError(f"Modbus read failed at {point.address}")
        return decode(result.registers, point)

    async def async_read(self):
        values = {}
        for point in self.points:
            try:
                value = await self._read_point(point)
                if value is not None:
                    values[point.key] = value
            except Exception as err:
                _LOGGER.warning("Ouman point %s unavailable: %s", point.key, err)
        return values

    async def async_write(self, point: Register, value: float):
        if not self.data.get(CONF_ALLOW_WRITES, False):
            raise ValueError("Writes were not enabled during configuration")
        if point.area != "holding":
            raise ValueError("Input registers cannot be written")
        # encode enforces the fixed, model-verified register write allowlist.
        raw = encode(float(value), point)
        if self.client is None or not self.client.connected:
            raise ConnectionError("Modbus disconnected")
        if len(raw) == 1:
            response = await self.client.write_register(
                point.address - 1, raw[0], device_id=self.data[CONF_UNIT_ID]
            )
        else:
            response = await self.client.write_registers(
                point.address - 1, raw, device_id=self.data[CONF_UNIT_ID]
            )
        if response.isError():
            raise ValueError("Modbus write returned exception")
        actual = await self._read_point(point)
        if abs(actual - float(value)) > (0.5 / 10 ** point.decimals + 1e-6):
            raise ValueError(f"Setpoint read-back mismatch: {actual!r}")

    async def async_close(self):
        if self.client is not None:
            self.client.close()
            self.client = None

class HttpDriver:
    """EH-800 HTTP via the same verified library as HA core's integration."""
    def __init__(self, hass, data):
        self.data = data
        self.hass = hass
        self.client = None
        self.registry = None
        self.endpoints = {}
        self.points = []

    async def async_connect(self):
        from ouman_eh_800_api import OumanEh800Client, IntControlOumanEndpoint, FloatControlOumanEndpoint
        self.client = OumanEh800Client(
            session=async_get_clientsession(self.hass),
            address=self.data[CONF_URL],
            username=self.data[CONF_USERNAME],
            password=self.data[CONF_PASSWORD],
        )
        await self.client.login()
        self.registry = await self.client.get_active_registries()
        self.endpoints = {ep.name: ep for ep in self.registry.endpoints}
        writable_prefixes = ("l1_curve_", "l2_curve_", "l1_water_out_", "l2_water_out_",
                             "l1_room_temperature_setpoint_user", "l2_room_temperature_setpoint_user")
        self.points = []
        for ep in self.registry.endpoints:
            is_number = isinstance(ep, (FloatControlOumanEndpoint, IntControlOumanEndpoint))
            can_write = is_number and ep.name.startswith(writable_prefixes)
            self.points.append(Register(
                key=ep.name, name=ep.name.replace("_", " ").capitalize(),
                address=0, kind="s16", decimals=0 if isinstance(ep, IntControlOumanEndpoint) else 1,
                unit=str(ep.unit) if ep.unit else None,
                minimum=ep.min_val if can_write else None,
                maximum=ep.max_val if can_write else None,
                writable=can_write,
            ))

    async def async_read(self):
        if self.client is None or self.registry is None:
            raise ConnectionError("HTTP controller unavailable")
        values = await self.client.get_values(self.registry)
        return {ep.name: val for ep, val in values.items()}

    async def async_write(self, point: Register, value: float):
        if not self.data.get(CONF_ALLOW_WRITES, False) or not point.writable:
            raise ValueError("HTTP setpoint not enabled for editing")
        if not point.minimum <= value <= point.maximum:
            raise ValueError("Setpoint outside documented bounds")
        await self.client.set_endpoint_value(self.endpoints[point.key], float(value))

    async def async_close(self):
        if self.client is not None:
            try:
                await self.client.logout()
            except Exception:
                _LOGGER.debug("EH-800 logout not available", exc_info=True)
            self.client = None

class UsbDriver:
    """EH-800B: shared locked USB reader and explicit manual setpoint writes.

    The legacy serial hub owns one port-level lock across read/write calls.
    No SET PROPERTY is sent on setup, refresh, reconnect or discovery.
    """

    def __init__(self, hass, data):
        from custom_components.ouman_eh800.ouman import OumanUSB
        from .usb_setpoints import USB_SAFE_SETPOINTS

        self.hass = hass
        self.data = data
        self.hub = OumanUSB(data[CONF_PORT])
        self.last_confirmed_writes = {}
        self.points = []
        names = {
            1: "L1 calculated supply target",
            9: "L1 supply water temperature",
            10: "Outdoor temperature",
            11: "Adjusted outdoor temperature",
            15: "L1 calculated valve position",
            16: "L1 valve position",
            21: "Delayed outdoor temperature",
        }
        for i in range(1, 29):
            unit = "%" if i in (15, 16) else "°C" if i in (1, 9, 10, 11, 21) else None
            self.points.append(Register(
                f"measurement_{i}", names.get(i, f"Measurement {i}"), i,
                "s16", 0, unit,
            ))
        # Only confirmed/allowlisted properties get Number entities. Their
        # CURRENT value cannot be read by a safe GET command on this model.
        # Do NOT synthesize defaults or use SET PROPERTY to discover values.
        for spec in USB_SAFE_SETPOINTS:
            self.points.append(Register(
                spec.key, spec.name, spec.property_id, "s16",
                spec.decimals, spec.unit, spec.minimum, spec.maximum, True,
            ))

    async def async_connect(self):
        # Read-only connection check performed by async_read.
        return

    async def async_read(self):
        measurements = await self.hass.async_add_executor_job(self.hub.measurements)
        result = {f"measurement_{i}": row[0]
                  for i, row in enumerate(measurements, start=1)}
        return {**result, **self.last_confirmed_writes}

    def _write_once(self, prop_id: int, wire_raw: int):
        from .usb_setpoints import confirm_property_reply

        # The legacy hub's _command takes the same per-port RLock as its
        # measurements() call. Explicit retries=1 prevents repeat writes
        # after a missing/garbled response. A failed response is ambiguous.
        response = self.hub._command(
            f"SET PROPERTY {prop_id} {wire_raw}", wait=0.18, retries=1
        )
        confirm_property_reply(prop_id, wire_raw, response)

    async def async_write(self, point: Register, value: float):
        from .usb_setpoints import USB_BY_KEY, raw_from_value

        spec = USB_BY_KEY.get(point.key)
        if spec is None or not point.writable or point.address != spec.property_id:
            raise ValueError("Unknown or prohibited EH-800B property")
        if self.data.get(CONF_MODEL) != "EH-800B":
            raise ValueError("EH-800B write adapter used with wrong device")
        raw = raw_from_value(spec, value)
        await self.hass.async_add_executor_job(self._write_once, spec.property_id,
                                               raw & 0xFFFF)
        # Report only last acknowledged user command. This is NOT a
        # side-effect-free live read; remains unknown before first write.
        self.last_confirmed_writes[spec.key] = raw / spec.scale

    async def async_close(self):
        return

def make_transport(hass, data):
    protocol = data[CONF_TRANSPORT]
    if protocol == "http":
        return HttpDriver(hass, data)
    if protocol == "usb":
        return UsbDriver(hass, data)
    if protocol == "bacnet_ip":
        from .extended_transports import BacnetDriver
        return BacnetDriver(hass, data)
    if protocol == "mbus_serial":
        from .extended_transports import MbusDriver
        return MbusDriver(hass, data)
    if protocol in ("modbus_tcp", "modbus_rtu"):
        return ModbusDriver(data)
    raise ValueError(f"Unsupported OpenLVI protocol: {protocol}")
