"""Tosi/Tosibox offline gateway monitoring and VPN-topology regression tests."""
from pathlib import Path
import json
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from openlvi_lab.tosibox import (
    interpret_gateway_registers, design_connection, REGISTER_MAP,
    firmware_version
)

def sample():
    return json.loads((ROOT / "examples/openlvi-lab/tosibox-snapshot.json")
                      .read_text(encoding="utf-8"))

class TosiboxTests(unittest.TestCase):
    def snapshot(self, data):
        return interpret_gateway_registers(
            data["registers"], gateway_model=data["gateway_model"],
            firmware=data["firmware"], observed_at=data["observed_at"],
            now=data.get("now"), target_reachable=data.get("target_reachable"),
        )

    def test_all_status_offsets_and_unavailable(self):
        result = self.snapshot(sample())
        self.assertEqual(result["fields"]["internet_interface"]["value"], "wan")
        self.assertEqual(result["fields"]["vpn_tunnel_count"]["value"], 2)
        self.assertTrue(result["fields"]["vpn_access_enabled"]["value"])
        self.assertEqual(result["fields"]["cellular_rsrp_raw"]["quality"], "unavailable")
        self.assertNotIn("value", result["fields"]["cellular_rsrp_raw"])
        self.assertEqual(result["fields"]["firmware_major"]["value"], 5)
        self.assertEqual(result["fields"]["firmware_minor"]["value"], 12)
        self.assertEqual(result["fields"]["firmware_patch"]["value"], 0)
        self.assertEqual(result["fields"]["vpn_access_enabled"]["manufacturer_offset"], 20)
        self.assertEqual(result["fields"]["vpn_access_enabled"]["openlvi_address"], 21)
        self.assertTrue(result["vpn_tunnel_count_not_a_reachability_test"])
        self.assertFalse(result["modbus_writes_enabled"])
        self.assertEqual(result["commands_issued"], 0)

    def test_firmware_version_gate_and_no_extra_registers(self):
        row=sample()
        row["firmware"]="5.5.0"
        first=self.snapshot(row)
        self.assertNotIn("firmware_major", first["fields"])
        self.assertEqual(len(first["fields"]), 7)
        row["firmware"]="5.4.9"
        with self.assertRaises(ValueError):
            self.snapshot(row)
        self.assertEqual(firmware_version("26.6.0"), (26, 6, 0))
        row["firmware"]="26.6.0"
        extra=dict(row["registers"], **{"24": 45012, "47": 1, "49": 8192})
        row["registers"]=extra
        out=self.snapshot(row)
        self.assertEqual(len(out["fields"]), 10)
        self.assertTrue(out["sensitive_identity_registers_ignored"])
        self.assertEqual(max(x["manufacturer_offset"] for x in out["fields"].values()), 23)

    def test_connection_state_caveats_and_alerts(self):
        row=sample()
        row["registers"].update({"16":0,"17":0,"18":0,"20":0})
        row["target_reachable"]=False
        out=self.snapshot(row)
        self.assertEqual(out["fields"]["vpn_tunnel_count"]["value"], 0)
        codes={x["code"] for x in out["network_findings"]}
        self.assertEqual(codes,{
            "gateway_no_wan", "vpn_administration_disabled",
            "vendor_coordination_unavailable","ot_target_unreachable",
        })
        self.assertEqual(out["tosi_vpn_connections_established"], 0)

    def test_zero_vpn_tunnels_alone_does_not_mean_outage(self):
        row=sample()
        row["registers"]["18"]=0
        out=self.snapshot(row)
        self.assertEqual(out["network_findings"], [])

    def test_staleness_does_not_report_old_status_as_current(self):
        row=sample()
        row["observed_at"]="2026-11-03T10:00:00Z"
        row["registers"]["16"]=0
        out=self.snapshot(row)
        self.assertEqual(out["snapshot_quality"],"stale")
        self.assertEqual(out["network_findings"], [])
        self.assertEqual(out["fields"]["internet_interface"]["quality"],"stale")

    def test_no_probe_invalid_registry_and_bounds(self):
        row=sample()
        for bad in (True, -1, 65536, "unknown"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                altered={**row, "registers": {**row["registers"],"16":bad}}
                self.snapshot(altered)
        for model in ("Unknown VPN box", "TOSIBOX 999"):
            with self.subTest(model=model), self.assertRaises(ValueError):
                self.snapshot({**row,"gateway_model":model})
        for key in ("nonsense", "-5"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.snapshot({**row,"registers":{key:1}})
        self.assertNotIn(47, REGISTER_MAP)
        self.assertNotIn(24, REGISTER_MAP)

    def test_connection_plan_requires_separate_authenticated_vpn(self):
        p=design_connection(deployment="multi_site",gateway_mode="lock",
                            monitoring_location="central")
        self.assertEqual(p["preferred"], "local_edge_plus_licensed_tosi_hub")
        self.assertEqual(p["commands_issued"],0)
        self.assertTrue(p["pure_vendor_cloud_independence_unverified"])
        with self.assertRaises(ValueError):
            design_connection(deployment="many",gateway_mode="client",
                              monitoring_location="central")

    def test_cli_reads_simulated_snapshot_only(self):
        script=ROOT/"tools/openlvi_lab_cli.py"
        commands=[
            ["tosibox-status","--input",str(ROOT/"examples/openlvi-lab/tosibox-snapshot.json")],
            ["tosibox-plan","--deployment","few_sites",
             "--gateway-mode","lock","--monitoring-location","on_site"],
        ]
        for args in commands:
            proc=subprocess.run([sys.executable,str(script),*args],
                                capture_output=True,text=True,timeout=25)
            self.assertEqual(proc.returncode,0,proc.stderr)
            self.assertEqual(json.loads(proc.stdout)["commands_issued"],0)

if __name__ == "__main__":
    unittest.main()
