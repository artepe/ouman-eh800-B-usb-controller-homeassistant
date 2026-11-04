"""Portable unit tests for BACnet/M-Bus profile safety and diagnostics."""
import importlib.util
from pathlib import Path
import sys
import types
import unittest
import json
from decimal import Decimal

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "openhvac"
package = types.ModuleType("openhvac")
package.__path__ = [str(ROOT)]
sys.modules.setdefault("openhvac", package)

def load(name):
    full = f"openhvac.{name}"
    spec = importlib.util.spec_from_file_location(full, ROOT / f"{name}.py")
    obj = importlib.util.module_from_spec(spec)
    sys.modules[full] = obj
    spec.loader.exec_module(obj)
    return obj

load("profiles")
drivers = load("extended_transports")
metrics = load("diagnostics")

class ExtendedTests(unittest.TestCase):
    def test_bacnet_allowlist(self):
        points = drivers.parse_bacnet_objects(json.dumps({"objects":[
            {"key":"room","type":"analog-input","instance":1,"unit":"°C"}
        ]}))
        self.assertEqual(points[0]["type"], "analog-input")
        with self.assertRaises(ValueError):
            drivers.parse_bacnet_objects('{"objects":[{"key":"x","type":"device","instance":2}]}')
        with self.assertRaises(ValueError):
            drivers.parse_bacnet_objects('{"objects":[{"key":"x","type":"analog-value","instance":0,"writable":true},{"key":"x","type":"analog-input","instance":1}]}')

    def test_mbus_records(self):
        class Record:
            def __init__(self, value, unit):
                self.value, self.unit = value, unit
        pts, values = drivers.mbus_records_to_values([
            Record(Decimal("321.25"), "kWh"), Record(12.5, "m³"),
        ])
        self.assertEqual(values["record_1"], 321.25)
        self.assertEqual(pts[1].unit, "m³")
        self.assertFalse(pts[0].writable)

    def test_temperature_delta_and_power(self):
        result = metrics.derive_plant_metrics({
            "l1_supply": 55, "l1_return": 50, "flow_m3h": 2.0})
        self.assertEqual(result["l1_delta_t"], 5)
        self.assertAlmostEqual(result["l1_thermal_power_kw"], 11.63)
        self.assertEqual(metrics.derive_plant_metrics({"l1_supply": 55}), {})
        self.assertEqual(metrics.derive_plant_metrics({"flow_m3h": "nan", "l1_supply":55,"l1_return":50}).get("l1_thermal_power_kw"), None)

    def test_diag_is_advice_not_control(self):
        warnings = metrics.diagnostic_notes({"l1_supply": 30, "l1_return": 63})
        self.assertTrue(warnings)
        self.assertFalse(metrics.diagnostic_notes({"l1_supply":50,"l1_return":45}))

if __name__ == "__main__":
    unittest.main()
