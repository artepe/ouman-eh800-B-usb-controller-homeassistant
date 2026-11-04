"""Offline regression tests for unit handling, M-Bus records, Uponor °F,
profile validation, Modbus cycle abort and refrigerant phase checks.

No Home Assistant installation and no hardware are required.
"""
import asyncio
from decimal import Decimal
import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "openhvac"
package = types.ModuleType("openhvac")
package.__path__ = [str(COMPONENT)]
sys.modules.setdefault("openhvac", package)


def load(name):
    spec = importlib.util.spec_from_file_location(f"openhvac.{name}", COMPONENT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


units = load("units")
profiles = load("profiles")
drivers = load("extended_transports")


class Record:
    """Stand-in for a pyMeterBus record, using the library's unit spellings."""

    def __init__(self, value, unit):
        self.value, self.unit = value, unit


class UnitTests(unittest.TestCase):
    def test_library_spellings_are_normalised(self):
        self.assertEqual(units.normalize_unit("C"), "°C")
        self.assertEqual(units.normalize_unit("m^3"), "m³")
        self.assertEqual(units.normalize_unit("m^3/h"), "m³/h")
        self.assertEqual(units.normalize_unit("°C"), "°C")
        self.assertEqual(units.normalize_unit("kWh"), "kWh")
        for empty in (None, "", "None", "date time", "date"):
            with self.subTest(unit=empty):
                self.assertIsNone(units.normalize_unit(empty))

    def test_prefixes_are_not_case_folded(self):
        # mW (milliwatt) must never become MW (megawatt).
        self.assertEqual(units.normalize_unit("mW"), "mW")
        self.assertEqual(units.normalize_unit("MWh"), "MWh")

    def test_device_and_state_classes(self):
        self.assertEqual(units.sensor_classes("°C"), ("temperature", "measurement"))
        self.assertEqual(units.sensor_classes("°F"), ("temperature", "measurement"))
        self.assertEqual(units.sensor_classes("kWh"), ("energy", "total_increasing"))
        self.assertEqual(units.sensor_classes("m³"), ("volume", "total_increasing"))
        self.assertEqual(units.sensor_classes("kW"), ("power", "measurement"))
        self.assertEqual(units.sensor_classes("m³/h"), ("volume_flow_rate", "measurement"))
        self.assertEqual(units.sensor_classes("%"), (None, "measurement"))
        self.assertEqual(units.sensor_classes(None), (None, None))

    def test_kelvin_difference_is_not_an_absolute_temperature(self):
        # As an absolute temperature HA would convert 5 K to -268 °C.
        self.assertEqual(units.sensor_classes("K"), ("temperature_delta", "measurement"))


class MbusRecordTests(unittest.TestCase):
    def test_units_and_non_numeric_records(self):
        points, values = drivers.mbus_records_to_values([
            Record(300000, "Wh"),
            Record(Decimal("1.5"), "m^3"),
            Record(Decimal("30"), "C"),
            Record("2026-11-04T10:00", "date time"),
            Record(float("nan"), "W"),
        ])
        by_key = {p.key: p for p in points}
        self.assertEqual(by_key["record_1"].unit, "Wh")
        self.assertEqual(by_key["record_2"].unit, "m³")
        self.assertEqual(by_key["record_3"].unit, "°C")
        self.assertEqual(values["record_3"], 30.0)
        # A date has no unit, otherwise HA rejects the non-numeric state.
        self.assertIsNone(by_key["record_4"].unit)
        self.assertEqual(values["record_4"], "2026-11-04T10:00")
        self.assertNotIn("record_5", values)
        self.assertTrue(all(not p.writable for p in points))
        self.assertTrue(all("mittaus" not in p.name for p in points))

    @unittest.skipUnless(importlib.util.find_spec("meterbus"), "pyMeterBus not installed")
    def test_real_pymeterbus_telegram(self):
        import meterbus
        records = bytes.fromhex(
            "04062C010000"   # energy, kWh
            "0413E8030000"   # volume, litres
            "025A2C01"       # flow temperature, 0.1 °C
            "046D1A2B3C1D")  # date and time
        body = bytes.fromhex("080172785634122D2C010401000000") + records
        frame = (bytes([0x68, len(body), len(body), 0x68]) + body
                 + bytes([sum(body) & 0xFF, 0x16]))
        points, values = drivers.mbus_records_to_values(meterbus.load(frame).records)
        units_by_key = {p.key: p.unit for p in points}
        self.assertEqual(units_by_key["record_1"], "Wh")
        self.assertEqual(units_by_key["record_2"], "m³")
        self.assertEqual(units_by_key["record_3"], "°C")
        self.assertAlmostEqual(values["record_3"], 30.0)
        self.assertIsNone(units_by_key["record_4"])
        self.assertIsInstance(values["record_4"], str)


class ProfileTests(unittest.TestCase):
    def test_uponor_x148_reports_fahrenheit(self):
        points = {p.key: p for p in profiles.profile_for("Smatrix Base PRO X-148", "", "")}
        outdoor = points["controller_outdoor_temp"]
        room = points["room_1_temperature"]
        self.assertEqual(outdoor.unit, "°F")
        self.assertEqual(room.unit, "°F")
        # Uponor manual: 21.0 °C is sent as 698 (69.8 °F).
        self.assertAlmostEqual(profiles.decode([698], room), 69.8)
        self.assertAlmostEqual((profiles.decode([698], room) - 32) / 1.8, 21.0)
        self.assertIsNone(profiles.decode([0x7FFF], room))

    def test_uponor_humidity_uses_low_byte_only(self):
        humidity = {p.key: p for p in profiles.profile_for(
            "Smatrix Base PRO X-148", "", "")}["room_1_humidity"]
        self.assertEqual(humidity.unit, "%")
        self.assertEqual(profiles.decode([0x0137], humidity), 0x37)
        self.assertEqual(profiles.decode([45], humidity), 45)
        self.assertIsNone(profiles.decode([0x7FFF], humidity))

    def test_masked_points_stay_read_only(self):
        point = profiles.parse_profile(json.dumps({"registers": [
            {"key": "rh", "name": "RH", "address": 14, "kind": "u16",
             "mask": 255, "unit": "%"}]}))[0]
        self.assertEqual(point.mask, 255)
        with self.assertRaises(ValueError):
            profiles.encode(10, profiles.Register(
                "x", "x", 1, "u16", 0, None, 0, 100, True, mask=255))

    def test_incomplete_profiles_raise_value_error(self):
        bad_items = (
            {"key": "a", "address": 1},                      # no name
            {"name": "a", "address": 1},                     # no key
            {"key": "a", "name": "a"},                       # no address
            {"key": "a", "name": "a", "address": 1, "kind": 5},
            {"key": "a", "name": "a", "address": 1, "unit": 42},
            {"key": "a", "name": "a", "address": 1, "mask": 0},
            {"key": "a", "name": "a", "address": 1, "kind": "u32", "mask": 255},
        )
        for item in bad_items:
            with self.subTest(item=item), self.assertRaises(ValueError):
                profiles.parse_profile(json.dumps({"registers": [item]}))


class FakeResult:
    def __init__(self, registers=None, error=False):
        self.registers = registers or []
        self._error = error

    def isError(self):
        return self._error


class FakeModbusClient:
    """Answers some addresses, rejects others, times out on the rest."""

    def __init__(self, answers, rejected=(), silent=()):
        self.answers, self.rejected, self.silent = answers, set(rejected), set(silent)
        self.connected = True
        self.requests = []

    async def _read(self, address, count, device_id):
        self.requests.append(address)
        if address in self.silent:
            raise TimeoutError("no response")
        if address in self.rejected:
            return FakeResult(error=True)
        return FakeResult([self.answers[address]])

    read_holding_registers = _read
    read_input_registers = _read


def load_transport():
    for name in ("homeassistant", "homeassistant.helpers"):
        if name not in sys.modules:
            module = types.ModuleType(name)
            module.__path__ = []
            sys.modules[name] = module
    if "homeassistant.helpers.aiohttp_client" not in sys.modules:
        http = types.ModuleType("homeassistant.helpers.aiohttp_client")
        http.async_get_clientsession = lambda hass: None
        sys.modules["homeassistant.helpers.aiohttp_client"] = http
    return load("transport")


def custom_profile(count):
    return json.dumps({"registers": [
        {"key": f"p{i}", "name": f"Point {i}", "address": i + 1}
        for i in range(count)
    ]})


class ModbusCycleTests(unittest.TestCase):
    def setUp(self):
        self.transport = load_transport()

    def make_driver(self, count, client):
        driver = self.transport.ModbusDriver({
            "model": "Custom", "firmware": "", "transport": "modbus_tcp",
            "unit_id": 1, "profile_json": custom_profile(count),
        })
        driver.client = client
        return driver

    def test_silent_device_stops_cycle_early(self):
        client = FakeModbusClient({}, silent=range(100))
        driver = self.make_driver(20, client)
        with self.assertLogs("openhvac.transport", "WARNING") as logs:
            values = asyncio.run(driver.async_read())
        self.assertEqual(values, {})
        self.assertEqual(len(client.requests), self.transport.MAX_SILENT_POINTS)
        self.assertIn("20 of 20", logs.output[0])

    def test_rejected_points_do_not_abort_the_cycle(self):
        client = FakeModbusClient({i: 200 + i for i in range(10)},
                                  rejected=(0, 1, 2, 3))
        driver = self.make_driver(10, client)
        with self.assertLogs("openhvac.transport", "WARNING"):
            values = asyncio.run(driver.async_read())
        self.assertEqual(len(client.requests), 10)
        self.assertEqual(sorted(values), [f"p{i}" for i in range(4, 10)])

    def test_unchanged_failures_are_logged_once(self):
        client = FakeModbusClient({i: 1 for i in range(5)}, rejected=(4,))
        driver = self.make_driver(5, client)
        with self.assertLogs("openhvac.transport", "WARNING") as logs:
            asyncio.run(driver.async_read())
        self.assertEqual(len(logs.output), 1)
        with self.assertNoLogs("openhvac.transport", "WARNING"):
            asyncio.run(driver.async_read())


class RefrigerantPhaseTests(unittest.TestCase):
    @staticmethod
    def tool():
        spec = importlib.util.spec_from_file_location(
            "openhvac_r290_phase", ROOT / "tools" / "refrigerant_state_calculator.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    @staticmethod
    def props(output, k1, p_pa, k2, value, fluid):
        if output == "H":
            return 400000 if p_pa == 400000 else (460000 if value > 343.15 else 200000)
        return 273.15 if p_pa == 400000 else 323.15  # dew / bubble points

    def test_wet_suction_is_rejected_clearly(self):
        with self.assertRaisesRegex(ValueError, "superheat"):
            self.tool().calculate("R290", 4, -1, 17, 90, 17, 45, props=self.props)

    def test_no_subcooling_is_rejected_clearly(self):
        with self.assertRaisesRegex(ValueError, "subcool"):
            self.tool().calculate("R290", 4, 3, 17, 90, 17, 51, props=self.props)


if __name__ == "__main__":
    unittest.main()
