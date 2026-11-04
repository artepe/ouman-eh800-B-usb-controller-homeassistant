"""Offline deterministic tests of the optional R290 enthalpy diagnostic."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools/refrigerant_state_calculator.py"
spec = importlib.util.spec_from_file_location("openhvac_r290_tool", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fake_props(output, k1, p_pa, k2, value, fluid):
    if fluid != "R290":
        raise ValueError("Wrong sample fluid")
    if k1 != "P":
        raise ValueError("Wrong state input")
    if output == "H":
        if p_pa == 400000:
            return 400000
        if p_pa == 1700000:
            return 460000 if value > 343.15 else 200000
    if output == "T" and k2 == "Q":
        if p_pa == 400000 and value == 1:
            return 273.15
        if p_pa == 1700000 and value == 0:
            return 323.15
    raise ValueError("Unexpected property lookup")


class R290ToolTests(unittest.TestCase):
    def test_sample_cycle_no_mass_flow_does_not_claim_measured_cop(self):
        r = module.calculate(
            "R290", 4, 3, 17, 90, 17, 45, props=fake_props
        )
        self.assertEqual(r["enthalpy_suction_kj_kg"], 400)
        self.assertEqual(r["enthalpy_discharge_kj_kg"], 460)
        self.assertEqual(r["enthalpy_condenser_out_kj_kg"], 200)
        self.assertEqual(r["superheat_k"], 3)
        self.assertEqual(r["subcooling_k"], 5)
        self.assertEqual(r["cycle_heating_cop_estimate"], 4.333)
        self.assertNotIn("condenser_thermal_kw", r)
        self.assertNotIn("compressor_electrical_heating_cop", r)

    def test_power_and_compressor_cop_requires_real_mass_flow(self):
        r = module.calculate(
            "R290", 4, 3, 17, 90, 17, 45,
            mass_flow_kg_s=.03, compressor_electric_kw=1.6,
            props=fake_props,
        )
        self.assertEqual(r["condenser_thermal_kw"], 7.8)
        self.assertEqual(r["compressor_electrical_heating_cop"], 4.875)

    def test_pressures_must_be_absolute_and_physical(self):
        for args in (
            ("R290", 0, 3, 17, 90, 17, 45),
            ("R290", 17, 3, 4, 90, 17, 45),
            ("R290", 4, 3, 17, 90, 2, 45),
            ("R290", float("nan"), 3, 17, 90, 17, 45),
            ("Unknown", 4, 3, 17, 90, 17, 45),
        ):
            with self.subTest(args=args), self.assertRaises(ValueError):
                module.calculate(*args, props=fake_props)

    def test_high_co2_alarm_is_notification_only(self):
        text = (ROOT / "blueprints/automation/openhvac/co2_high_alert.yaml"
                ).read_text(encoding="utf-8")
        self.assertIn("persistent_notification.create", text)
        self.assertIn("numeric_state", text)
        self.assertNotIn("light.turn_on", text)
        self.assertNotIn("number.set_value", text)
        self.assertNotIn("modbus.write", text)


if __name__ == "__main__":
    unittest.main()
