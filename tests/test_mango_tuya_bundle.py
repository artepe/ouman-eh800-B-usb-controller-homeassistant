"""Verify that the standalone local Mango heat-pump integration is complete.

No Home Assistant import, Tuya connection or controller write is performed.
"""
from pathlib import Path
import json
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "mango_tuya_local"


class MangoTuyaBundleTests(unittest.TestCase):
    def test_local_manifest_and_profile(self):
        manifest = json.loads((COMPONENT / "manifest.json").read_text(encoding="utf-8"))
        profile = json.loads((COMPONENT / "profile.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["domain"], "mango_tuya_local")
        self.assertEqual(manifest["iot_class"], "local_polling")
        self.assertTrue(any("tinytuya" in req for req in manifest["requirements"]))
        self.assertEqual(profile["parameter_count"], 770)
        self.assertEqual(profile["section_count"], 17)
        self.assertEqual(len(profile["routes"]), 770)
        self.assertEqual(len(profile["sections"]), 17)

    def test_bundled_resources(self):
        for relative in (
            "__init__.py", "client.py", "protocol.py", "coordinator.py",
            "config_flow.py", "profile.json", "descriptions.json",
            "frontend/mango-parameter-card.js", "translations/en.json",
            "translations/fi.json",
        ):
            with self.subTest(relative=relative):
                self.assertTrue((COMPONENT / relative).is_file())


if __name__ == "__main__":
    unittest.main()
