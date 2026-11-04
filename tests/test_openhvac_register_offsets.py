"""Offline tests for documented read-only register engineering-unit offsets."""
import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE_DIR = ROOT / "custom_components" / "openhvac"
pkg = types.ModuleType("openhvac")
pkg.__path__ = [str(MODULE_DIR)]
sys.modules.setdefault("openhvac", pkg)
spec = importlib.util.spec_from_file_location("openhvac.profiles", MODULE_DIR / "profiles.py")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class OffsetTests(unittest.TestCase):
    def test_vallox_centikelvin_conversion(self):
        profile = module.parse_profile(json.dumps({"registers": [
            {"key": "supply_temperature", "name": "Supply air",
             "address": 4358, "area": "holding", "kind": "u16",
             "decimals": 2, "offset": -273.15, "unit": "°C"}]}))
        self.assertEqual(len(profile), 1)
        self.assertFalse(profile[0].writable)
        self.assertAlmostEqual(module.decode([29315], profile[0]), 20.0)

    def test_signed_negative_and_old_profiles(self):
        old = module.Register("outdoor", "Outdoor", 201)
        self.assertEqual(module.decode([65526], old), -1.0)
        with self.assertRaises(ValueError):
            module.encode(20, module.Register(
                "unsafe", "No write", 4358, minimum=0, maximum=500,
                writable=True, offset=-273.15))

    def test_invalid_offsets_rejected(self):
        for value in ["bad", True, 1e100, -1001, None]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                module.parse_profile(json.dumps({"registers": [
                    {"key": "temp", "name": "Temperature",
                     "address": 4358, "offset": value}]}))

    def test_example_is_only_reading(self):
        profile = json.loads((ROOT / "examples" /
                              "modbus-myvallox-readonly.json").read_text())
        all_points = module.parse_profile(json.dumps(profile))
        self.assertTrue(all(not p.writable for p in all_points))
        self.assertTrue(any(p.offset == -273.15 for p in all_points))


if __name__ == "__main__":
    unittest.main()
