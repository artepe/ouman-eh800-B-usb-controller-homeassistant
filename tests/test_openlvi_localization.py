"""Regression tests: English canonical text and six separate Ouman locales.

No HA dependencies and no hardware connections. Verifies translation data
without renaming any USB property IDs, stable entity identifiers or writes.
"""
import ast
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "openlvi"
LOCALES = ("en", "fi", "sv", "et", "pl", "ru")
SETPOINT_KEYS = (
    "l1_supply_minimum", "l1_supply_maximum",
    "l1_curve_minus_20c", "l1_curve_minus_10c", "l1_curve_0c",
    "l1_curve_plus_10c", "l1_curve_plus_20c",
    "l1_summer_shutoff", "l1_max_supply_change_rate",
    "l1_supply_setpoint", "l1_fine_adjustment",
)
SENSOR_KEYS = (
    *(f"eh800b_measurement_{index}" for index in range(1, 29)),
    "derived_l1_delta_t", "derived_l1_thermal_power_kw",
    "derived_water_heating_power_kw", "derived_system_heating_cop",
    "derived_water_compressor_heating_cop",
    "derived_refrigerant_cycle_heating_cop_estimate",
    "derived_refrigerant_heating_power_kw",
    "derived_refrigerant_compressor_heating_cop",
    "diagnostics", "english_ai_guide",
)
NUMBER_KEYS = tuple("eh800b_" + x for x in SETPOINT_KEYS)
BUTTON_KEYS = ("review_settings_en",)


def load_json(name):
    return json.loads((COMPONENT / name).read_text(encoding="utf-8"))


def leaves(value, path=()):
    if isinstance(value, dict):
        for key, item in value.items():
            yield from leaves(item, path + (key,))
    else:
        yield path, value


class LocaleTests(unittest.TestCase):
    def test_english_source_is_canonical(self):
        self.assertEqual(load_json("strings.json"),
                         load_json("translations/en.json"))
        self.assertEqual(
            load_json("strings.json")["config"]["step"]["user"]["title"],
            "Choose manufacturer",
        )

    def test_six_locales_have_identical_keys(self):
        english = load_json("strings.json")
        required = set(path for path, _ in leaves(english))
        for locale in LOCALES:
            with self.subTest(locale=locale):
                obj = load_json(f"translations/{locale}.json")
                self.assertEqual(set(path for path, _ in leaves(obj)), required)
                for _, text in leaves(obj):
                    self.assertIsInstance(text, str)
                    self.assertTrue(text.strip())

    def test_all_ouman_usb_entities_are_localized(self):
        for lang in LOCALES:
            with self.subTest(locale=lang):
                obj = load_json(f"translations/{lang}.json")["entity"]
                self.assertEqual(set(obj["sensor"]), set(SENSOR_KEYS))
                self.assertEqual(set(obj["number"]), set(NUMBER_KEYS))
                self.assertEqual(set(obj["button"]), set(BUTTON_KEYS))

    def test_entity_unique_identifiers_and_writes_unchanged(self):
        number = (COMPONENT / "number.py").read_text(encoding="utf-8")
        sensor = (COMPONENT / "sensor.py").read_text(encoding="utf-8")
        transport = (COMPONENT / "transport.py").read_text(encoding="utf-8")
        setpoints = (COMPONENT / "usb_setpoints.py").read_text(encoding="utf-8")
        for source in (number, sensor):
            ast.parse(source)
        self.assertIn("_{point.key}_number", number)
        self.assertIn("_{point.key}_sensor", sensor)
        self.assertIn("SET PROPERTY {prop_id} {wire_raw}", transport)
        self.assertIn("56, 57, 58, 92", setpoints)
        self.assertIn('f"eh800b_{point.key}"', number)
        self.assertIn('f"eh800b_{point.key}"', sensor)

    def test_manifest_version_and_legacy_unchanged(self):
        self.assertEqual(load_json("manifest.json")["version"], "0.4.4-beta.1")
        legacy = json.loads((ROOT / "custom_components/ouman_eh800/manifest.json")
                            .read_text(encoding="utf-8"))
        self.assertEqual(legacy["version"], "0.1.2")


if __name__ == "__main__":
    unittest.main()
