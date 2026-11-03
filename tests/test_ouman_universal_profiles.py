"""No Home Assistant installation is required for these pure register tests."""
import importlib.util
from pathlib import Path
import unittest

MODULE = Path(__file__).resolve().parents[1] / "custom_components" / "ouman_universal" / "profiles.py"
spec = importlib.util.spec_from_file_location("ouman_profiles", MODULE)
import sys
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)

class ProfileTests(unittest.TestCase):
    def test_ouman_address_base(self):
        points = mod.profile_for("A203", "2.0.2", "")
        self.assertEqual(points[0].address - 1, 200)

    def test_signed_16_and_scale(self):
        p = mod.Register("x", "x", 201)
        self.assertEqual(mod.decode([0xff9c], p), -10.0)

    def test_signed_32_high_word_first(self):
        p = mod.Register("x", "x", 305, "s32", 1)
        self.assertEqual(mod.decode([0xffff, 0xff9c], p), -10.0)

    def test_documented_model_specific_room_setpoints(self):
        expected = {
            "A203": ("2.0.2", 818, 905, 50),
            "S203": ("3.0.10", 793, 713, 50),
            "C203": ("3.0.10", 585, 751, 50),
            "H23": ("4.0.5", 432, 453, 35),
        }
        for model, (firmware, l1, l2, maximum) in expected.items():
            with self.subTest(model=model):
                points = mod.profile_for(model, firmware, "")
                targets = {p.key: p for p in points if p.writable}
                self.assertEqual(targets["l1_room_target"].address, l1)
                self.assertEqual(targets["l2_room_target"].address, l2)
                self.assertEqual(targets["l1_room_target"].maximum, maximum)

    def test_unknown_fw_requires_profile(self):
        with self.assertRaises(ValueError):
            mod.profile_for("S203", "3.0.11", "")

    def test_custom_profile_cannot_write(self):
        p = mod.parse_profile('{"registers":[{"key":"x","name":"X","address":5,"writable":true}]}')
        self.assertFalse(p[0].writable)
        with self.assertRaises(ValueError):
            mod.encode(22.5, p[0])

    def test_verified_write_scale(self):
        p = next(x for x in mod.PROFILE_MAPS["A203"] if x.key == "l1_room_target")
        self.assertEqual(mod.encode(21.5, p), [215])
        with self.assertRaises(ValueError):
            mod.encode(55, p)

if __name__ == "__main__":
    unittest.main()
