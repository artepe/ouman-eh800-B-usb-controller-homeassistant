"""EH-203 MODBUS-200 register map tests; no HA or device required."""
import importlib.util
from pathlib import Path
import sys
import unittest

MODULE = Path(__file__).resolve().parents[1] / "custom_components" / "openlvi" / "profiles.py"
spec = importlib.util.spec_from_file_location("openlvi_eh203_profiles", MODULE)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


class EH203ProfileTests(unittest.TestCase):
    def test_manual_zero_based_registers_are_shifted_once(self):
        points = {point.key: point for point in mod.profile_for("EH-203", "2.18c", "")}
        self.assertEqual(points["outdoor"].address, 232)
        self.assertEqual(points["l1_supply"].address, 233)
        self.assertEqual(points["l1_valve"].address, 243)
        self.assertEqual(points["alarms_254_raw"].address, 255)
        self.assertEqual(points["general_alarm_raw"].address, 273)
        # The driver subtracts one before sending an FC03 request.
        self.assertEqual(points["outdoor"].address - 1, 231)

    def test_temperatures_and_valves_have_distinct_scaling(self):
        points = {point.key: point for point in mod.profile_for("EH-203", "1.30", "")}
        self.assertEqual(mod.decode([0xFB2E], points["outdoor"]), -12.34)
        self.assertEqual(mod.decode([5234], points["l1_supply"]), 52.34)
        self.assertEqual(mod.decode([77], points["l1_valve"]), 77.0)
        self.assertEqual(mod.decode([0x8001], points["alarms_254_raw"]), 32769.0)

    def test_every_builtin_point_is_read_only(self):
        for firmware in ("1.22", "1.30", "2.0", "2.18c"):
            with self.subTest(firmware=firmware):
                points = mod.profile_for("EH-203", firmware, "")
                self.assertGreater(len(points), 8)
                self.assertTrue(all(p.area == "holding" and not p.writable for p in points))
                for point in points:
                    with self.assertRaises(ValueError):
                        mod.encode(20, point)

    def test_unsupported_or_missing_firmware_rejected(self):
        for firmware in ("", "1.21", "3.0", "2.18-preview", "abc"):
            with self.subTest(firmware=firmware), self.assertRaises(ValueError):
                mod.profile_for("EH-203", firmware, "")

    def test_explicit_custom_map_remains_read_only(self):
        points = mod.profile_for("EH-203", "unknown",
                                 '{"registers":[{"key":"x","name":"Site point",'
                                 '"address":232,"writable":true}]}')
        self.assertEqual(len(points), 1)
        self.assertFalse(points[0].writable)


if __name__ == "__main__":
    unittest.main()
