"""Contract checks for Danfoss MCX and DEVIreg zone price support."""
from pathlib import Path
import importlib.util
import json
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "custom_components" / "openlvi"
package = types.ModuleType("openlvi")
package.__path__ = [str(BASE)]
sys.modules.setdefault("openlvi", package)

def load(name):
    spec = importlib.util.spec_from_file_location("openlvi." + name, BASE / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module

constants = load("const")
profiles = load("profiles")

class DanfossMCXTests(unittest.TestCase):
    def test_model_is_selectable_but_has_no_guessed_registers(self):
        self.assertIn("MCX (site-programmed)", constants.VENDOR_MODELS["Danfoss"])
        with self.assertRaises(ValueError):
            profiles.profile_for("MCX (site-programmed)", "v02.0", "")

    def test_operator_mcx_profile_stays_read_only(self):
        points = profiles.profile_for("MCX (site-programmed)", "v02.0",
             json.dumps({"registers": [
                 {"key": "zone1", "name": "Site verified zone 1",
                  "address": 123, "kind": "s16", "decimals": 1, "writable": True}
             ]}))
        self.assertEqual(points[0].address, 123)
        self.assertFalse(points[0].writable)
        with self.assertRaises(ValueError):
            profiles.encode(21.0, points[0])

    def test_blueprint_is_one_circuit_and_fails_to_normal(self):
        p = ROOT / "blueprints/automation/openlvi/devireg330_price_setback.yaml"
        content = p.read_text(encoding="utf-8")
        for marker in ("domain: automation", "setback_switch: !input setback_switch",
                       "switch.turn_on", "switch.turn_off", "max_age_minutes",
                       "platform: homeassistant", "platform: time_pattern",
                       "not is_number(price)"):
            self.assertIn(marker, content)
        self.assertNotIn("modbus.write_register", content)
        self.assertNotIn("switch.toggle", content)

if __name__ == "__main__":
    unittest.main()
