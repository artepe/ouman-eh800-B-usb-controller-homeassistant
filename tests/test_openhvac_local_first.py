"""Offline local-first HVAC and Zigbee bridge tests; no physical I/O."""
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from openhvac_lab.local_hvac import UNIT_MAP, plan_local_path, normalize_heatpump_entities
from openhvac_lab.zigbee import zigbee_mesh_audit


def example(name):
    return json.loads((ROOT / "examples" / "openhvac-lab" / name).read_text(encoding="utf-8"))


class LocalFirstTests(unittest.TestCase):
    def test_comfort_cloud_and_aquarea_cloud_are_not_local(self):
        for path in ("panasonic_comfort_cloud", "panasonic_aquarea_smart_cloud"):
            with self.subTest(path=path):
                plan = plan_local_path(path)
                self.assertEqual(plan["strict_local_policy"], "blocked")
                self.assertEqual(plan["runtime"], "cloud_required")
                self.assertFalse(plan["local_runtime_eligible"])
                with self.assertRaises(ValueError):
                    normalize_heatpump_entities(path, states={}, mapping={},
                                                now="2026-11-04T09:00:00Z")

    def test_local_methods_are_not_falsely_hardware_verified(self):
        for path in ("mango_r290_tuya_local", "chinese_oem_modbus",
                     "panasonic_split_esphome", "panasonic_aquarea_heishamon",
                     "panasonic_aquarea_m_modbus", "midea_msmart_local",
                     "gree_lan", "mitsubishi_ecodan_cn105", "daikin_lan"):
            with self.subTest(path=path):
                report = plan_local_path(path)
                self.assertTrue(report["local_runtime_eligible"])
                self.assertFalse(report["verified_no_internet"])
                self.assertEqual(report["commands_issued"], 0)
                self.assertFalse(report["writes_enabled"])
        p = plan_local_path("chinese_oem_modbus",
                            physical_interface_verified=True, verified_wan_offline=True)
        self.assertTrue(p["verified_no_internet"])
        with self.assertRaises(ValueError):
            plan_local_path("unknown_vendor_generic")

    def test_mango_example_converts_only_verified_units(self):
        p = example("local-heatpump.json")
        result = normalize_heatpump_entities(
            p["path"], states=p["states"], mapping=p["mapping"], now=p["now"])
        self.assertEqual(result["measurements"]["electric_power_kw"]["value"], 1.62)
        self.assertEqual(result["measurements"]["water_flow_m3h"]["value"], 2.08)
        self.assertEqual(result["measurements"]["compressor_speed_rps"]["value"], 34)
        self.assertIs(result["measurements"]["defrost_active"]["value"], False)
        self.assertEqual(result["measurements"]["supply_c"]["quality"], "fresh")
        self.assertEqual(result["register_writes"], 0)
        self.assertNotIn("cop", result)

    def test_invalid_unit_missing_source_and_stale_readings(self):
        p = example("local-heatpump.json")
        p["states"]["sensor.demo_heatpump_supply"]["unit"] = "°F"
        p["states"]["sensor.demo_heatpump_return"]["last_updated"] = "2026-11-03T06:00:00Z"
        del p["states"]["sensor.demo_heatpump_outdoor"]
        report = normalize_heatpump_entities(
            p["path"], states=p["states"], mapping=p["mapping"], now=p["now"])
        self.assertEqual(report["measurements"]["supply_c"]["quality"], "invalid_unit")
        self.assertEqual(report["measurements"]["return_c"]["quality"], "stale")
        self.assertEqual(report["measurements"]["outdoor_c"]["quality"], "missing")

    def test_unknown_dps_and_write_entities_are_rejected(self):
        p = example("local-heatpump.json")
        for mapping in ({"setpoint_write": "sensor.demo_heatpump_supply"},
                        {"supply_c": "climate.panasonic_2"},
                        {"supply_c": "number.heatpump_target"}):
            with self.subTest(mapping=mapping), self.assertRaises(ValueError):
                normalize_heatpump_entities(
                    p["path"], states=p["states"], mapping=mapping, now=p["now"])
        self.assertNotIn("tuya_dp_704", UNIT_MAP)

    def test_boolean_must_be_actual_boolean_on_off(self):
        p = example("local-heatpump.json")
        p["states"]["binary_sensor.demo_heatpump_defrost"]["state"] = "unknown"
        report = normalize_heatpump_entities(
            p["path"], states=p["states"], mapping=p["mapping"], now=p["now"])
        self.assertEqual(report["measurements"]["defrost_active"]["quality"], "invalid")

    def test_zigbee_mesh_uses_existing_coordinator(self):
        p = example("zigbee-mesh.json")
        report = zigbee_mesh_audit(p["mesh"], now=p["now"])
        self.assertEqual(report["backend"], "zigbee2mqtt")
        self.assertEqual(report["coordinator_count"], 1)
        self.assertFalse(report["clone_protocol_stack"])
        self.assertEqual(report["commands_issued"], 0)
        self.assertIn("low_lqi", [x["code"] for x in report["findings"]])

    def test_zigbee_duplicate_coordinator_cloud_invalid(self):
        p = example("zigbee-mesh.json")
        for bad in (0, 2):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                zigbee_mesh_audit(dict(p["mesh"], coordinator_count=bad),
                                  now=p["now"])
        with self.assertRaises(ValueError):
            zigbee_mesh_audit(dict(p["mesh"], uses_vendor_cloud=True), now=p["now"])
        devices = p["mesh"]["devices"] + [p["mesh"]["devices"][0]]
        with self.assertRaises(ValueError):
            zigbee_mesh_audit(dict(p["mesh"], devices=devices), now=p["now"])

    def test_cli_local_paths_and_mango_normalization(self):
        script = ROOT / "tools" / "openhvac_lab_cli.py"
        for args in (
            ["local-hvac-path", "--path", "panasonic_comfort_cloud"],
            ["local-hvac-path", "--path", "mango_r290_tuya_local"],
            ["local-heatpump-readings", "--input",
             str(ROOT / "examples/openhvac-lab/local-heatpump.json")],
            ["zigbee-audit", "--input",
             str(ROOT / "examples/openhvac-lab/zigbee-mesh.json")],
        ):
            proc = subprocess.run([sys.executable, str(script), *args],
                                  capture_output=True, text=True, timeout=20)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(json.loads(proc.stdout)["commands_issued"], 0)


if __name__ == "__main__":
    unittest.main()
