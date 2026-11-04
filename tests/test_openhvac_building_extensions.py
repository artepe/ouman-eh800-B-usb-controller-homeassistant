"""Read-only tests for additional Finnish building controllers and energy math."""
from pathlib import Path
import importlib.util
import json
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "custom_components" / "openhvac"
package = types.ModuleType("openhvac")
package.__path__ = [str(BASE)]
sys.modules.setdefault("openhvac", package)


def mod(name):
    spec = importlib.util.spec_from_file_location(f"openhvac.{name}", BASE / f"{name}.py")
    obj = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = obj
    spec.loader.exec_module(obj)
    return obj


profiles = mod("profiles")
engineering = mod("engineering")
constants = mod("const")


class BuildingProfilesTests(unittest.TestCase):
    def test_uponor_x148_fc04_channel_address_and_missing(self):
        p = profiles.profile_for("Smatrix Base PRO X-148", "", "")
        self.assertEqual(len(p), 25)
        self.assertEqual(p[0].key, "controller_outdoor_temp")
        self.assertEqual(p[0].area, "input")
        self.assertEqual(p[0].address - 1, 0)  # PDF 30001 => PDU 0
        self.assertEqual(p[1].address - 1, 1)  # PDF 30002 => PDU 1
        self.assertAlmostEqual(profiles.decode([215], p[1]), 21.5)
        self.assertIsNone(profiles.decode([0x7fff], p[1]))
        self.assertTrue(all(not x.writable for x in p))

    def test_roth_touchline_proven_first_zone_registers(self):
        p = {x.key: x for x in profiles.profile_for("Touchline SL Modbus", "", "")}
        self.assertEqual(p["zone_1_temperature"].address, 23)
        self.assertEqual(p["zone_1_floor_temperature"].address, 74)
        self.assertEqual(p["zone_1_humidity"].address, 122)
        self.assertEqual(p["zone_1_actuator_open"].address, 170)
        self.assertEqual(p["zone_1_target"].address, 221)
        self.assertAlmostEqual(profiles.decode([224], p["zone_1_temperature"]), 22.4)
        self.assertFalse(p["zone_1_target"].writable)

    def test_tosibox_uses_vendor_offsets_and_excludes_commands(self):
        p = profiles.profile_for("TOSIBOX 610", "5.5.0", "")
        ids = {x.address for x in p}
        self.assertEqual(ids, set(range(15, 22)))
        self.assertTrue(all(not x.writable for x in p))
        self.assertIsNone(profiles.decode([0xffff], p[0]))
        self.assertNotIn(48, ids)  # SMS send command (vendor offset 47)
        with self.assertRaises(ValueError):
            profiles.profile_for("TOSIBOX 610", "", "")
        with self.assertRaises(ValueError):
            profiles.profile_for("TOSIBOX 610", "5.4.9", "")
        p2 = profiles.profile_for("TOSIBOX 610", "5.6.0", "")
        self.assertIn(24, {x.address for x in p2})

    def test_missing_raw_sentinel_only_for_read_only(self):
        good = profiles.parse_profile(json.dumps({"registers": [
            {"key": "a", "name": "a", "address": 10,
             "invalid_raw_values": [65535]}]}))[0]
        self.assertFalse(good.writable)
        self.assertIsNone(profiles.decode([65535], good))
        self.assertEqual(profiles.decode([120], good), 120)
        for value in ([-1], [65536], [True], ["65535"], [2, 2], list(range(9))):
            with self.subTest(value=value), self.assertRaises(ValueError):
                profiles.parse_profile(json.dumps({"registers": [
                    {"key": "a", "name": "a", "address": 10,
                     "invalid_raw_values": value}]}))

    def test_extended_model_list_is_discovery_not_auto_writes(self):
        for manufacturer in ("Ouman", "Tosibox", "Uponor", "Roth", "Wavin",
                             "Honeywell", "Resideo", "Siemens", "Danfoss"):
            self.assertIn(manufacturer, constants.VENDOR_MODELS)
        with self.assertRaises(ValueError):
            profiles.profile_for("Smatrix Pulse R-208", "", "")
        with self.assertRaises(ValueError):
            profiles.profile_for("Evohome", "", "")
        with self.assertRaises(ValueError):
            profiles.profile_for("Desigo PXC4", "", "")


class EngineeringTests(unittest.TestCase):
    def test_water_power_and_system_vs_compressor_cop(self):
        q = engineering.water_heating_power_kw(2.08, 52, 49)
        self.assertAlmostEqual(q, 7.23084267, places=4)
        self.assertAlmostEqual(engineering.heating_cop(q, 1.6), q / 1.6)
        result = engineering.derive_cop_metrics({
            "flow_m3h": 2.08, "l1_supply": 52, "l1_return": 49,
            "electric_power_kw": 2.0,
            "compressor_electric_power_kw": 1.6,
        })
        self.assertIn("system_heating_cop", result)
        self.assertIn("water_compressor_heating_cop", result)
        self.assertGreater(result["water_compressor_heating_cop"],
                           result["system_heating_cop"])

    def test_cycle_thermodynamics_vs_measured_electrical_cop(self):
        self.assertAlmostEqual(
            engineering.refrigerant_cycle_heating_cop(400, 460, 200), 260 / 60)
        self.assertAlmostEqual(
            engineering.refrigerant_heating_power_kw(.03, 460, 200), 7.8)
        d = engineering.derive_cop_metrics({
            "refrigerant_suction_enthalpy_kj_kg": 400,
            "refrigerant_discharge_enthalpy_kj_kg": 460,
            "refrigerant_liquid_enthalpy_kj_kg": 200,
            "refrigerant_mass_flow_kg_s": .03,
            "compressor_electric_power_kw": 1.6,
        })
        self.assertEqual(d["refrigerant_cycle_heating_cop_estimate"], 4.333)
        self.assertEqual(d["refrigerant_compressor_heating_cop"], 4.875)

    def test_incomplete_or_bad_measurements_do_not_invent_cop(self):
        self.assertEqual(engineering.derive_cop_metrics({}), {})
        self.assertEqual(engineering.derive_cop_metrics({
            "l1_supply": 52, "l1_return": 49, "electric_power_kw": 1.6
        }), {})
        for wrong in (0, -1, float("nan"), float("inf"), True):
            with self.subTest(wrong=wrong), self.assertRaises(ValueError):
                engineering.heating_cop(7.8, wrong)
        with self.assertRaises(ValueError):
            engineering.water_heating_power_kw(2, 40, 55)
        with self.assertRaises(ValueError):
            engineering.refrigerant_cycle_heating_cop(460, 400, 200)

    def test_blueprint_has_required_guards_and_is_auxiliary_only(self):
        blueprint = (
            ROOT / "blueprints/automation/openhvac/co2_supplemental_fan_0_10v.yaml"
        ).read_text(encoding="utf-8")
        for expected in (
            "domain: automation", "entity_id: !input enable_helper",
            "outdoor_cutoff_c:", "cold_hysteresis_c:", "co2_low",
            "minimum_change_percent:", "light.turn_on", "light.turn_off",
            "co2 is none", "outdoor is none", "not is_state(light_entity, 'on')",
        ):
            self.assertIn(expected, blueprint)
        self.assertIn("mandatory whole-building ventilation", blueprint)

    def test_english_localization_complete_after_cop_entities(self):
        entries = json.loads((BASE / "strings.json").read_text(encoding="utf-8"))
        for key in engineering.derive_cop_metrics({
            "flow_m3h": 2.08, "l1_supply": 52, "l1_return": 49,
            "electric_power_kw": 2, "compressor_electric_power_kw": 1.6,
            "refrigerant_mass_flow_kg_s": .03,
            "refrigerant_suction_enthalpy_kj_kg": 400,
            "refrigerant_discharge_enthalpy_kj_kg": 460,
            "refrigerant_liquid_enthalpy_kj_kg": 200,
        }):
            self.assertIn("derived_" + key, entries["entity"]["sensor"])


if __name__ == "__main__":
    unittest.main()
