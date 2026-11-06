"""Pure register profile tests for OpenLVI Bridge without HA runtime."""
import importlib.util
from pathlib import Path
import sys
import unittest

MODULE = Path(__file__).resolve().parents[1] / "custom_components" / "openlvi" / "profiles.py"
spec = importlib.util.spec_from_file_location("openlvi_vendor_profiles", MODULE)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)

class OpenLVIVendorProfiles(unittest.TestCase):
    def test_danfoss_s2_pnu_and_scale(self):
        for name in mod.DANFOSS_MODELS:
            with self.subTest(name=name):
                pts = mod.profile_for(name, "", "", "")
                self.assertEqual(len(pts), 1)
                self.assertEqual((pts[0].address, pts[0].area, pts[0].decimals), (10202, "holding", 2))
                self.assertFalse(pts[0].writable)
                self.assertEqual(mod.decode([2144], pts[0]), 21.44)

    def test_danfoss_application_key_limits_exposed_points(self):
        pts = mod.profile_for("ECL Comfort 310", "", "", "A266.1")
        self.assertEqual(pts[1].address, 11180)
        self.assertEqual(pts[1].decimals, 1)
        self.assertFalse(pts[1].writable)
        self.assertEqual(len(mod.profile_for("ECL Comfort 310", "", "", "A230")), 1)

    def test_swegon_input_vs_holding_and_write_allowlist(self):
        with self.assertRaises(ValueError):
            mod.profile_for("CASA Genius", "3.9", "", "")
        pts = mod.profile_for("CASA Genius", "4.3", "", "")
        lookup = {p.key: p for p in pts}
        self.assertEqual((lookup["supply_fan_rpm"].address, lookup["supply_fan_rpm"].area), (6305, "input"))
        self.assertEqual((lookup["operation_mode"].address, lookup["operation_mode"].area), (5001, "holding"))
        self.assertEqual(mod.encode(2, lookup["operation_mode"]), [2])
        with self.assertRaises(ValueError):
            mod.encode(0, lookup["operation_mode"])
        self.assertFalse(lookup["co2_home_limit"].writable)

    def test_regin_corrigo_e_vendor_scaling(self):
        with self.assertRaises(ValueError):
            mod.profile_for("Corrigo E Ventilation", "5.0", "", "")
        pts = {p.key: p for p in mod.profile_for("Corrigo E Ventilation", "3.2", "", "")}
        self.assertEqual((pts["supply_temp"].address, pts["supply_temp"].area, pts["supply_temp"].decimals), (7, "input", 1))
        self.assertEqual((pts["supply_flow"].address, pts["supply_flow"].decimals), (15, 0))
        self.assertEqual(mod.decode([0xffce], pts["outdoor_temp"]), -5)
        self.assertTrue(all(not p.writable for p in pts.values()))

    def test_tehowatti_air_requires_site_register_list_and_never_writes(self):
        with self.assertRaises(ValueError):
            mod.profile_for("Tehowatti AIR (MODBUS 40)", "", "", "")
        # This is a synthetic register to verify the generic profile parser,
        # NOT an assertion about any actual Tehowatti address.
        sample = ('{"registers":[{"key":"test_value","name":"Test only",'
                  '"address":1,"kind":"u16","writable":true}]}')
        points = mod.profile_for("Tehowatti AIR (MODBUS 40)", "", sample, "")
        self.assertEqual(len(points), 1)
        self.assertFalse(points[0].writable)
        with self.assertRaises(ValueError):
            mod.encode(10, points[0])

    def test_unmapped_vendor_requires_exact_register_list(self):
        with self.assertRaises(ValueError):
            mod.profile_for("Corrigo 5", "", "", "")
        with self.assertRaises(ValueError):
            mod.profile_for("MyVallox", "", "", "")

    def test_custom_read_only_input(self):
        pts = mod.profile_for("MyVallox", "", '{"registers":[{"key":"inlet","name":"Inlet","address":510,"area":"input","kind":"s16","decimals":1}]}')
        self.assertEqual(pts[0].area, "input")
        self.assertFalse(pts[0].writable)
        with self.assertRaises(ValueError):
            mod.parse_profile('{"registers":[{"key":"x","name":"Test","address":4,"area":"coil"}]}')

if __name__ == "__main__":
    unittest.main()
