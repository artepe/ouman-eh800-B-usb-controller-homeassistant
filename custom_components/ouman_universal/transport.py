"""Local HTTP, USB and Modbus drivers. No writes occur during discovery."""
from __future__ import annotations
import logging
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_MODEL, CONF_TRANSPORT, CONF_HOST, CONF_PORT, CONF_BAUDRATE,
    CONF_UNIT_ID, CONF_FIRMWARE, CONF_PROFILE, CONF_ALLOW_WRITES,
    CONF_URL, CONF_USERNAME, CONF_PASSWORD,
)
from .profiles import Register, profile_for, decode, encode

_LOGGER = logging.getLogger(__name__)

class ModbusDriver:
    def __init__(self, data):
        self.data = data
        self.points = profile_for(
            data[CONF_MODEL], data.get(CONF_FIRMWARE, ""), data.get(CONF_PROFILE, "")
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
                parity="N", stopbits=1, bytesize=8, timeout=4, retries=1
            )
        await self.client.connect()
        if not self.client.connected:
            raise ConnectionError("Modbus connection failed")

    async def _read_point(self, point: Register):
        if self.client is None or not self.client.connected:
            raise ConnectionError("Modbus disconnected")
        # Ouman PDFs use 1-based address notation, pymodbus uses 0-based.
        result = await self.client.read_holding_registers(
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
                values[point.key] = await self._read_point(point)
            except Exception as err:
                _LOGGER.warning("Ouman point %s unavailable: %s", point.key, err)
        return values

    async def async_write(self, point: Register, value: float):
        if not self.data.get(CONF_ALLOW_WRITES, False):
            raise ValueError("Writes were not enabled during configuration")
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
    """Read-only EH-800B adapter reusing the existing stable protocol reader."""
    def __init__(self, hass, data):
        self.hass = hass
        self.data = data
        self.hub = None
        try:
            from custom_components.ouman_eh800.ouman import OumanUSB
        except ImportError as err:
            raise RuntimeError("Install the original ouman_eh800 component alongside this one") from err
        self.hub = OumanUSB(data[CONF_PORT])
        names = {1:"L1 laskettu menovesipyynti", 9:"L1 menovesi", 10:"Ulkolämpötila",
                 11:"Korjattu ulkolämpötila",15:"L1 laskettu venttiiliasento",
                 16:"L1 venttiiliasento",21:"Hidastettu ulkolämpötila"}
        self.points = [
            Register(f"measurement_{i}", names.get(i, f"Mittaus {i}"), i,
                     "s16", 0, "%" if i in (15,16) else "°C" if i in (1,9,10,11,21) else None)
            for i in range(1,29)
        ]

    async def async_connect(self):
        # No command is sent until async_read.
        return

    async def async_read(self):
        result = await self.hass.async_add_executor_job(self.hub.measurements)
        return {f"measurement_{i}": row[0] for i, row in enumerate(result, start=1)}

    async def async_write(self, point, value):
        raise ValueError("USB write operations remain in the original EH-800B integration")

    async def async_close(self):
        return

def make_transport(hass, data):
    protocol = data[CONF_TRANSPORT]
    if protocol == "http":
        return HttpDriver(hass, data)
    if protocol == "usb":
        return UsbDriver(hass, data)
    if protocol in ("modbus_tcp", "modbus_rtu"):
        return ModbusDriver(data)
    raise ValueError(f"Unsupported Ouman protocol: {protocol}")
