"""Home Assistant level tests for the OpenHVAC config flow, setup and sensors.

All transports are faked in memory: no network, serial port or hardware.
"""
from decimal import Decimal
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

DOMAIN = "openhvac"

# Ouman A203 firmware 2.0.2 profile: vendor 1-based address -> raw value.
A203_REGISTERS = {201: 215, 202: 452, 203: 401, 205: 0, 208: 550, 209: 450,
                  818: 210, 905: 200}
# Uponor X-148: tenths of °F by default; 698 = 69.8 °F = 21.0 °C.
UPONOR_REGISTERS = {1: 302, **{i + 1: 698 for i in range(1, 13)},
                    **{i + 13: 0x0137 for i in range(1, 13)}}

MODBUS_TCP_ENTRY = {
    "vendor": "Ouman", "model": "A203", "firmware": "2.0.2",
    "application_key": "", "allow_writes": False, "transport": "modbus_tcp",
    "host": "192.168.1.50", "port": 502, "unit_id": 1, "profile_json": "",
}


class FakeResult:
    def __init__(self, registers=None):
        self.registers = registers or []

    def isError(self):
        return not self.registers


class FakeModbusClient:
    """Stands in for pymodbus' async TCP and serial clients."""

    registers: dict = A203_REGISTERS
    reachable = True

    def __init__(self, *args, **kwargs):
        self.connected = False

    async def connect(self):
        self.connected = self.reachable
        return self.connected

    async def read_holding_registers(self, address, count, device_id):
        raw = self.registers.get(address + 1)
        return FakeResult([raw] if raw is not None else [])

    read_input_registers = read_holding_registers

    def close(self):
        self.connected = False


def modbus_client(registers=A203_REGISTERS, reachable=True):
    return type("Client", (FakeModbusClient,),
                {"registers": registers, "reachable": reachable})


def patch_modbus(client):
    return (patch("pymodbus.client.AsyncModbusTcpClient", client),
            patch("pymodbus.client.AsyncModbusSerialClient", client))


async def start_modbus_flow(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["step_id"] == "user"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"vendor": "Ouman"})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"model": "A203", "firmware": "2.0.2",
                            "application_key": "", "allow_writes": False})
    assert result["step_id"] == "transport"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"transport": "modbus_tcp"})
    assert result["step_id"] == "connection"
    return result


CONNECTION = {"host": "192.168.1.50", "port": 502, "unit_id": 1, "profile_json": ""}


async def test_flow_creates_modbus_entry(hass):
    tcp, rtu = patch_modbus(modbus_client())
    with tcp, rtu, patch("custom_components.openhvac.async_setup_entry", return_value=True):
        result = await start_modbus_flow(hass)
        result = await hass.config_entries.flow.async_configure(result["flow_id"], CONNECTION)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Ouman A203"


async def test_flow_aborts_for_already_configured_device(hass):
    """AbortFlow must not be swallowed and reported as cannot_connect."""
    tcp, rtu = patch_modbus(modbus_client())
    with tcp, rtu, patch("custom_components.openhvac.async_setup_entry", return_value=True):
        first = await start_modbus_flow(hass)
        await hass.config_entries.flow.async_configure(first["flow_id"], CONNECTION)
        second = await start_modbus_flow(hass)
        result = await hass.config_entries.flow.async_configure(second["flow_id"], CONNECTION)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_flow_silent_device_is_a_connection_error(hass):
    tcp, rtu = patch_modbus(modbus_client(registers={}))
    with tcp, rtu:
        result = await start_modbus_flow(hass)
        result = await hass.config_entries.flow.async_configure(result["flow_id"], CONNECTION)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


class RejectingOumanClient:
    def __init__(self, *args, **kwargs):
        pass

    async def login(self):
        from ouman_eh_800_api.exceptions import OumanClientAuthenticationError
        raise OumanClientAuthenticationError("Wrong username or password")

    async def logout(self):
        return None


async def test_flow_wrong_eh800_password_is_reported(hass):
    with patch("ouman_eh_800_api.OumanEh800Client", RejectingOumanClient):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER})
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"vendor": "Ouman"})
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"model": "EH-800", "firmware": "",
                                "application_key": "", "allow_writes": False})
        assert result["step_id"] == "connection"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"url": "http://192.168.1.60", "username": "user",
                                "password": "wrong"})
    assert result["errors"] == {"base": "invalid_auth"}


async def test_offline_controller_is_retried(hass):
    """After a power cut HA may start before the controller: retry setup."""
    entry = MockConfigEntry(domain=DOMAIN, data=MODBUS_TCP_ENTRY)
    entry.add_to_hass(hass)
    tcp, rtu = patch_modbus(modbus_client(reachable=False))
    with tcp, rtu:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_rejected_eh800_credentials_are_a_config_error(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={
        "vendor": "Ouman", "model": "EH-800", "firmware": "",
        "application_key": "", "allow_writes": False, "transport": "http",
        "url": "http://192.168.1.60", "username": "user", "password": "old",
    })
    entry.add_to_hass(hass)
    with patch("ouman_eh_800_api.OumanEh800Client", RejectingOumanClient):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert "password" in (entry.reason or "")


def sensor_state(hass, entry, key):
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_{key}")
    assert entity_id, key
    return hass.states.get(entity_id)


async def test_modbus_sensors_keep_long_term_statistics(hass):
    entry = MockConfigEntry(domain=DOMAIN, data=MODBUS_TCP_ENTRY)
    entry.add_to_hass(hass)
    tcp, rtu = patch_modbus(modbus_client())
    with tcp, rtu:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        outdoor = sensor_state(hass, entry, "outdoor_sensor")
        assert float(outdoor.state) == 21.5
        assert outdoor.attributes["device_class"] == "temperature"
        assert outdoor.attributes["state_class"] == "measurement"
        delta = sensor_state(hass, entry, "derived_l1_delta_t")
        assert float(delta.state) == 5.1
        assert delta.attributes["state_class"] == "measurement"
        assert delta.attributes.get("device_class") != "temperature"
        assert await hass.config_entries.async_unload(entry.entry_id)


async def test_uponor_fahrenheit_is_shown_in_celsius(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={
        "vendor": "Uponor", "model": "Smatrix Base PRO X-148", "firmware": "",
        "application_key": "", "allow_writes": False, "transport": "modbus_rtu",
        "port": "/dev/ttyUSB0", "baudrate": 19200, "parity": "E", "unit_id": 1,
        "profile_json": "",
    })
    entry.add_to_hass(hass)
    tcp, rtu = patch_modbus(modbus_client(registers=UPONOR_REGISTERS))
    with tcp, rtu:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        room = sensor_state(hass, entry, "room_1_temperature_sensor")
        assert room.attributes["unit_of_measurement"] == "°C"
        assert abs(float(room.state) - 21.0) < 0.05
        humidity = sensor_state(hass, entry, "room_1_humidity_sensor")
        assert float(humidity.state) == 0x37
        assert await hass.config_entries.async_unload(entry.entry_id)


class Record:
    def __init__(self, value, unit):
        self.value, self.unit = value, unit


def fake_mbus_read(self):
    from custom_components.openhvac.extended_transports import mbus_records_to_values
    return mbus_records_to_values([
        Record(300000, "Wh"),
        Record(Decimal("12.5"), "m^3"),
        Record(Decimal("61.2"), "C"),
        Record("2026-11-04T10:00", "date time"),
    ])


async def test_kamstrup_records_have_ha_units_and_dates_load(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={
        "vendor": "Kamstrup", "model": "MULTICAL 603", "firmware": "",
        "application_key": "", "allow_writes": False, "transport": "mbus_serial",
        "port": "/dev/ttyUSB1", "baudrate": 2400, "unit_id": 1,
    })
    entry.add_to_hass(hass)
    with patch("custom_components.openhvac.extended_transports.MbusDriver._read_sync",
               fake_mbus_read):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        energy = sensor_state(hass, entry, "record_1_sensor")
        assert energy.attributes["device_class"] == "energy"
        assert energy.attributes["state_class"] == "total_increasing"
        volume = sensor_state(hass, entry, "record_2_sensor")
        assert volume.attributes["unit_of_measurement"] == "m³"
        temperature = sensor_state(hass, entry, "record_3_sensor")
        assert temperature.attributes["unit_of_measurement"] == "°C"
        date = sensor_state(hass, entry, "record_4_sensor")
        assert date.state == "2026-11-04T10:00"
        assert "unit_of_measurement" not in date.attributes
        assert await hass.config_entries.async_unload(entry.entry_id)


class FakeUsbHub:
    """Stands in for the bundled EH-800B USB client (no serial port)."""

    commands: list = []

    def __init__(self, port):
        self.port = port

    def measurements(self):
        return [(40.0 + index / 10, "C") for index in range(28)]

    def command(self, command, wait=0.18, retries=3):
        FakeUsbHub.commands.append((command, retries))
        _, _, prop_id, raw = command.split()
        return f"PROPERTY({prop_id}):'TEST'(0-1000) = {raw}"


async def test_eh800b_usb_uses_bundled_client_and_writes_once(hass):
    """No custom_components.ouman_eh800 import; one SET per user action."""
    FakeUsbHub.commands = []
    entry = MockConfigEntry(domain=DOMAIN, data={
        "vendor": "Ouman", "model": "EH-800B", "firmware": "",
        "application_key": "", "allow_writes": False, "transport": "usb",
        "port": "/dev/serial/by-id/usb-OUMAN_Ouman_EH-800-if00",
    })
    entry.add_to_hass(hass)
    with patch("custom_components.openhvac.ouman_usb.OumanUSB", FakeUsbHub):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        target = sensor_state(hass, entry, "measurement_1_sensor")
        assert float(target.state) == 40.0
        assert target.attributes["device_class"] == "temperature"
        registry = er.async_get(hass)
        curve = registry.async_get_entity_id(
            "number", DOMAIN, f"{entry.entry_id}_l1_curve_minus_20c_number")
        assert hass.states.get(curve).state == "unknown"
        assert FakeUsbHub.commands == []  # setup and polling never write
        await hass.services.async_call(
            "number", "set_value", {"entity_id": curve, "value": 55}, blocking=True)
        await hass.async_block_till_done()
        assert FakeUsbHub.commands == [("SET PROPERTY 67 550", 1)]
        assert float(hass.states.get(curve).state) == 55.0
        assert await hass.config_entries.async_unload(entry.entry_id)



async def test_derived_sensor_recovers_after_missing_first_poll(hass):
    """A partial first Modbus read must not permanently hide a COP/delta sensor."""
    missing_return = dict(A203_REGISTERS)
    del missing_return[203]
    fake = modbus_client(registers=missing_return)
    entry = MockConfigEntry(domain=DOMAIN, data=MODBUS_TCP_ENTRY)
    entry.add_to_hass(hass)
    tcp, rtu = patch_modbus(fake)
    with tcp, rtu:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        delta = sensor_state(hass, entry, "derived_l1_delta_t")
        assert delta.state in ("unknown", "unavailable")
        # The next poll recovers, without re-adding the HA integration.
        fake.registers = A203_REGISTERS
        await entry.runtime_data.async_request_refresh()
        await hass.async_block_till_done()
        assert float(sensor_state(hass, entry, "derived_l1_delta_t").state) == 5.1
        assert await hass.config_entries.async_unload(entry.entry_id)


async def test_modbus_read_reconnects_after_gateway_reboot(hass):
    """Reconnection happens on a READ, never by replaying an uncertain write."""
    from custom_components.openhvac.transport import ModbusDriver

    class ReconnectClient(FakeModbusClient):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.connect_calls = 0

        async def connect(self):
            self.connect_calls += 1
            self.connected = True
            return True

    driver = ModbusDriver(MODBUS_TCP_ENTRY)
    tcp, rtu = patch_modbus(ReconnectClient)
    with tcp, rtu:
        await driver.async_connect()
        assert driver.client.connect_calls == 1
        first = await driver.async_read()
        assert first["l1_supply"] == 45.2
        driver.client.connected = False
        recovered = await driver.async_read()
        assert recovered["l1_supply"] == 45.2
        assert driver.client.connect_calls == 2
        await driver.async_close()


async def test_modbus_write_does_not_reconnect_or_replay_command(hass):
    """After a broken connection, writing requires a separate successful read."""
    from custom_components.openhvac.transport import ModbusDriver
    from custom_components.openhvac.profiles import Register
    from unittest.mock import AsyncMock

    data = {**MODBUS_TCP_ENTRY, "allow_writes": True}
    driver = ModbusDriver(data)
    client = modbus_client()()
    client.connected = False
    client.connect = AsyncMock()
    client.write_register = AsyncMock()
    driver.client = client
    point = Register("test_setpoint", "Test", 201, "u16", 0, "°C",
                     minimum=0, maximum=80, writable=True)
    # The range/type encoder itself may reject a synthetic profile, so
    # fake only its verified conversion while testing transport behavior.
    with patch("custom_components.openhvac.transport.encode", return_value=[25]):
        try:
            await driver.async_write(point, 25)
        except ConnectionError:
            pass
        else:
            assert False, "Disconnected Modbus write should fail closed"
    client.connect.assert_not_awaited()
    client.write_register.assert_not_awaited()


async def test_usb_acknowledged_write_survives_unrelated_refresh_failure(hass):
    """Never tell the operator an ACKed SET failed because MEASUREMENTS timed out."""
    FakeUsbHub.commands = []
    entry = MockConfigEntry(domain=DOMAIN, data={
        "vendor": "Ouman", "model": "EH-800B", "firmware": "",
        "application_key": "", "allow_writes": False, "transport": "usb",
        "port": "/dev/serial/by-id/usb-OUMAN_Ouman_EH-800-if00",
    })
    entry.add_to_hass(hass)
    with patch("custom_components.openhvac.ouman_usb.OumanUSB", FakeUsbHub):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        curve = er.async_get(hass).async_get_entity_id(
            "number", DOMAIN, f"{entry.entry_id}_l1_curve_minus_20c_number")
        assert hass.states.get(curve).state == "unknown"
        with patch.object(entry.runtime_data, "async_request_refresh",
                          side_effect=RuntimeError("USB polling is offline")) as refresh:
            await hass.services.async_call(
                "number", "set_value", {"entity_id": curve, "value": 55},
                blocking=True,
            )
            await hass.async_block_till_done()
            refresh.assert_not_called()
        assert FakeUsbHub.commands == [("SET PROPERTY 67 550", 1)]
        assert float(hass.states.get(curve).state) == 55
        assert hass.states.get(curve).attributes["value_origin"] == "last_confirmed_user_write"
        assert await hass.config_entries.async_unload(entry.entry_id)

async def test_legacy_driver_hides_pid_and_valve_and_starts_unknown(hass):
    """Legacy ouman_eh800 0.1.3: no PID 56/57/58 or valve 92, no fake values."""
    from homeassistant.setup import async_setup_component

    class LegacyHub:
        def __init__(self, port):
            self.port = port

    with patch("custom_components.ouman_eh800.number.OumanUSB", LegacyHub):
        assert await async_setup_component(hass, "number", {
            "number": [{"platform": "ouman_eh800", "port": "/dev/ttyTEST"}]})
        await hass.async_block_till_done()
    registry = er.async_get(hass)
    legacy = [e for e in registry.entities.values() if e.platform == "ouman_eh800"]
    unique_ids = {e.unique_id for e in legacy}
    assert len(legacy) == 11
    for prop_id in (56, 57, 58, 92):
        assert f"ouman_eh800_property_{prop_id}" not in unique_ids
    assert all(hass.states.get(e.entity_id).state == "unknown" for e in legacy)
