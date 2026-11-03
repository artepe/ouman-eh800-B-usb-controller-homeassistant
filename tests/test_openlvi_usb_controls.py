"""EH-800B USB safe-controls tests without a Home Assistant installation."""
import asyncio
import importlib.util
from pathlib import Path
import re
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "openlvi"
package = types.ModuleType("openlvi")
package.__path__ = [str(ROOT)]
sys.modules.setdefault("openlvi", package)


def load(name):
    spec = importlib.util.spec_from_file_location(f"openlvi.{name}", ROOT / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


const = load("const")
profiles = load("profiles")
setpoints = load("usb_setpoints")


class SetpointTests(unittest.TestCase):
    def test_controls_have_unique_ids_and_forbidden_are_absent(self):
        self.assertEqual(len(setpoints.USB_SAFE_SETPOINTS), 11)
        self.assertFalse(set(setpoints.USB_BY_ID) & {56, 57, 58, 92})

    def test_numeric_range_and_steps(self):
        curve = setpoints.USB_BY_KEY["l1_curve_minus_20c"]
        self.assertEqual(setpoints.raw_from_value(curve, 55), 550)
        for value in [55.2, -1, 101, float("nan"), float("inf"), "bad"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                setpoints.raw_from_value(curve, value)
        fine = setpoints.USB_BY_KEY["l1_fine_adjustment"]
        self.assertEqual(setpoints.raw_from_value(fine, -0.1), -1)

    def test_replies_must_match_exact_property_and_value(self):
        setpoints.confirm_property_reply(
            67, 550, "PROPERTY(67):'L1_KAYRA'(0-1000) = 550"
        )
        setpoints.confirm_property_reply(
            134, 65535, "PROPERTY(134):'L1_HIENOSAATO'(-40-40) = -1"
        )
        for response in ["", "PROPERTY(56):'PID'(2-600) = 550",
                         "PROPERTY(67):'L1_KAYRA'(0-1000) = 500"]:
            with self.subTest(response=response), self.assertRaises(ValueError):
                setpoints.confirm_property_reply(67, 550, response)


class FakeHub:
    instances = []
    def __init__(self, port):
        self.port = port
        self.commands = []
        self.fail_reply = False
        self.__class__.instances.append(self)

    def measurements(self):
        return [(55.8, "C")] * 28

    def _command(self, cmd, wait=0.18, retries=3):
        self.commands.append((cmd, retries))
        if self.fail_reply:
            return "truncated"
        match = re.fullmatch(r"SET PROPERTY (\d+) (\d+)", cmd)
        if not match:
            raise ValueError("Unexpected command")
        pid, raw = map(int, match.groups())
        return f"PROPERTY({pid}):'TEST'(-40-1000) = {raw}"


async def run_driver_sequence():
    # Stub only the non-transport Home Assistant imports and the legacy
    # controller object. The real Hub is NOT called during CI.
    homeassistant = types.ModuleType("homeassistant")
    homeassistant.__path__ = []
    ha_helpers = types.ModuleType("homeassistant.helpers")
    ha_helpers.__path__ = []
    ha_http = types.ModuleType("homeassistant.helpers.aiohttp_client")
    ha_http.async_get_clientsession = lambda hass: None
    legacy_root = types.ModuleType("custom_components")
    legacy_root.__path__ = []
    legacy = types.ModuleType("custom_components.ouman_eh800")
    legacy.__path__ = []
    legacy_module = types.ModuleType("custom_components.ouman_eh800.ouman")
    legacy_module.OumanUSB = FakeHub
    for name, module in [
        ("homeassistant", homeassistant),
        ("homeassistant.helpers", ha_helpers),
        ("homeassistant.helpers.aiohttp_client", ha_http),
        ("custom_components", legacy_root),
        ("custom_components.ouman_eh800", legacy),
        ("custom_components.ouman_eh800.ouman", legacy_module),
    ]:
        sys.modules[name] = module

    transport = load("transport")

    class FakeHass:
        async def async_add_executor_job(self, fn, *args):
            return fn(*args)

    driver = transport.UsbDriver(FakeHass(), {
        "model": "EH-800B", "port": "/dev/ttyTEST", "transport": "usb",
        "allow_writes": False,
    })
    hub = driver.hub
    await driver.async_connect()
    first = await driver.async_read()
    assert len(first) == 28, first
    assert not hub.commands, "Setup/read must never run SET PROPERTY"
    assert not any(k.startswith("l1_curve_") for k in first)

    points = {p.key: p for p in driver.points}
    assert len(driver.points) == 28 + 11
    assert all(key not in points for key in ["l1_p_band", "l1_i_time",
                                            "l1_d_time", "l1_manual_valve_position"])

    await driver.async_write(points["l1_curve_minus_20c"], 55)
    assert hub.commands == [("SET PROPERTY 67 550", 1)]
    updated = await driver.async_read()
    assert updated["l1_curve_minus_20c"] == 55
    assert len(hub.commands) == 1, "Polling must never repeat a SET"

    # A garbled reply must not cause a second write, nor claim success.
    hub.fail_reply = True
    try:
        await driver.async_write(points["l1_curve_minus_20c"], 56)
        raise AssertionError("Garbled response accepted")
    except ValueError:
        pass
    assert hub.commands[-1] == ("SET PROPERTY 67 560", 1)
    assert len(hub.commands) == 2
    assert (await driver.async_read())["l1_curve_minus_20c"] == 55

    bad = profiles.Register("pid", "PID", 56, minimum=0,
                            maximum=600, writable=True)
    try:
        await driver.async_write(bad, 200)
        raise AssertionError("Prohibited PID write accepted")
    except ValueError:
        pass
    assert len(hub.commands) == 2


class TransportTests(unittest.TestCase):
    def test_mock_driver_with_one_write_only(self):
        asyncio.run(run_driver_sequence())


if __name__ == "__main__":
    unittest.main()
