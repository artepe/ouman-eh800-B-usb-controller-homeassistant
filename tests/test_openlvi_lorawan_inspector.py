"""Offline regression tests for independent read-only LoRaWAN envelope inspector."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "lorawan_uplink_inspect.py"
spec = importlib.util.spec_from_file_location("openlvi_lorawan_uplink_inspect", SCRIPT)
inspector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inspector)


class UplinkTests(unittest.TestCase):
    def load(self, name):
        path = ROOT / "examples" / "lorawan" / name
        return json.loads(path.read_text(encoding="utf-8"))

    def test_milesight_ug65_envelope(self):
        r = inspector.inspect_uplink(self.load("milesight-ug65-uplink.example.json"))
        self.assertEqual(r["format"], "milesight_embedded_ns")
        self.assertEqual(r["dev_eui"], "24e1641092176759")
        self.assertEqual(r["f_port"], 85)
        self.assertEqual(r["frame_counter"], 8)
        self.assertEqual(r["rssi_dbm"], -57)
        self.assertEqual(r["snr_db"], 10)
        self.assertEqual(r["payload_hex"], "01670000026800")
        self.assertEqual(r["decoded_fields"], {})

    def test_chirpstack_v4_decoded_only(self):
        r = inspector.inspect_uplink(self.load("chirpstack-v4-uplink.example.json"))
        self.assertEqual(r["format"], "chirpstack_v4")
        self.assertEqual(r["payload_hex"], "aa")
        self.assertEqual(r["decoded_fields"]["temperature"], 21.5)
        self.assertEqual(r["rssi_dbm"], -36)

    def test_tts_v3_decoded_only(self):
        r = inspector.inspect_uplink(self.load("tts-v3-uplink.example.json"))
        self.assertEqual(r["format"], "the_things_stack_v3")
        self.assertEqual(r["payload_hex"], "01020304")
        self.assertEqual(r["decoded_fields"], {"temperature": 20.5})

    def test_invalid_inputs_fail_closed(self):
        base = self.load("milesight-ug65-uplink.example.json")
        variants = [
            {"hello": "world"},
            {**base, "devEUI": "wrong"},
            {**base, "fPort": 0},
            {**base, "fPort": True},
            {**base, "fCnt": True},
            {**base, "fCnt": -1},
            {**base, "data": "not-base64??"},
            {**base, "data": ""},
            {**base, "data": "A" * 4000},
        ]
        for payload in variants:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                inspector.inspect_uplink(payload)

    def test_codecs_not_guessed_for_binary_payload(self):
        base = self.load("milesight-ug65-uplink.example.json")
        raw = inspector.inspect_uplink(base)
        self.assertNotIn("temperature", raw["decoded_fields"])
        self.assertNotIn("leak", raw["decoded_fields"])
        self.assertNotIn("battery", raw["decoded_fields"])

    def test_bounded_vendor_fields(self):
        base = self.load("milesight-ug65-uplink.example.json")
        base["object"] = {
            "temperature": 22.5, "leak": True, "firmware": "demo",
            "nested": {"do_not_forward": "x"}, "large": "x" * 500
        }
        r = inspector.inspect_uplink(base)
        self.assertEqual(r["decoded_fields"], {
            "temperature": 22.5, "leak": True, "firmware": "demo"
        })

    def test_cli_parses_local_fixture(self):
        sample = ROOT / "examples" / "lorawan" / "milesight-ug65-uplink.example.json"
        proc = subprocess.run([sys.executable, str(SCRIPT), str(sample)],
                              check=True, capture_output=True, text=True)
        self.assertEqual(json.loads(proc.stdout)["format"], "milesight_embedded_ns")

    def test_no_network_or_write_side_effects(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("mosquitto_pub", source)
        self.assertNotIn("paho.mqtt", source)
        self.assertNotIn("asyncio.open_connection", source)


if __name__ == "__main__":
    unittest.main()
