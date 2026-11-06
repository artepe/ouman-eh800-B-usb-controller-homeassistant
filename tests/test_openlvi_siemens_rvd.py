"""Offline Siemens RVD120/RVD140 FC03 mapping and engineering-unit tests."""
import importlib.util
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "custom_components" / "openlvi"
pkg = types.ModuleType("openlvi")
pkg.__path__ = [str(DIR)]
sys.modules.setdefault("openlvi", pkg)
spec = importlib.util.spec_from_file_location("openlvi.profiles", DIR / "profiles.py")
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


class SiemensRVDTests(unittest.TestCase):
    def test_models_and_exact_wire_addresses(self):
        for model, code in (("RVD120", 140), ("RVD140", 142)):
            with self.subTest(model=model):
                points = mod.profile_for(model, "", "")
                self.assertGreater(len(points), 20)
                self.assertTrue(all(not p.writable and p.area == "holding" for p in points))
                self.assertEqual(len(points), len({p.key for p in points}))
                p = {x.key: x for x in points}
                self.assertEqual(p["controller_model_code"].address - 1, 1021)
                self.assertEqual(p["outdoor_temp"].address - 1, 1044)
                self.assertEqual(p["flow_temp"].address - 1, 1045)
                self.assertEqual(p["primary_return_temp"].address - 1, 1048)
                self.assertEqual(p["flow_target"].address - 1, 1064)
                self.assertEqual(mod.decode([code], p["controller_model_code"]), code)

    def test_signed_64th_degree_encoding(self):
        p = {x.key: x for x in mod.profile_for("RVD120", "", "")}
        self.assertEqual(mod.decode([0x0140], p["outdoor_temp"]), 5)
        self.assertEqual(mod.decode([0xFEC0], p["outdoor_temp"]), -5)
        self.assertEqual(mod.decode([0x0D80], p["flow_temp"]), 54)
        self.assertEqual(mod.decode([1], p["flow_temp"]), 1 / 64)

    def test_rvd140_optional_pressures(self):
        rvd120 = {x.key for x in mod.profile_for("RVD120", "", "")}
        p = {x.key: x for x in mod.profile_for("RVD140", "", "")}
        self.assertNotIn("secondary_pressure", rvd120)
        self.assertEqual(p["secondary_pressure"].address - 1, 1052)
        self.assertEqual(mod.decode([500], p["secondary_pressure"]), 10)
        self.assertEqual(mod.decode([275], p["primary_pressure"]), 5.5)
        self.assertEqual(mod.decode([10], p["modbus_version"]), 1)

    def test_no_siemens_commands_even_with_opt_in(self):
        p = {x.key: x for x in mod.profile_for("RVD140", "", "")}
        for key in ("fault_code", "flow_temp", "room_target", "hardware_write_lock"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                mod.encode(20, p[key])
        forced = mod.Register("test", "Unsafe", 1045, "s16", 0, "°C",
                              0, 100, True, read_scale=1 / 64)
        with self.assertRaises(ValueError):
            mod.encode(40, forced)

    def test_other_vendor_decimal_scaling_unchanged(self):
        old = mod.profile_for("CASA Genius", "4.3", "")
        self.assertTrue(old)
        p = mod.Register("test", "Standard", 12)
        self.assertEqual(mod.decode([250], p), 25)


if __name__ == "__main__":
    unittest.main()
