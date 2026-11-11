"""Portable tests for Open HVAC module archives and download-branch inputs."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import package_modules as mod  # noqa: E402


class ModuleDistributionTests(unittest.TestCase):
    def test_catalog_has_safe_unique_modules(self):
        modules = mod.module_catalog()
        self.assertEqual(len(modules), 6)
        self.assertEqual(len({x["slug"] for x in modules}), len(modules))
        self.assertNotIn("ezviz", json.dumps(modules).lower())

    def test_all_integrations_have_valid_manifests(self):
        for module in mod.module_catalog():
            if module["kind"] != "integration":
                continue
            for folder in (p for p in module["paths"] if p.startswith("custom_components/")):
                with self.subTest(folder=folder):
                    manifest = json.loads((ROOT / folder / "manifest.json").read_text(encoding="utf-8"))
                    self.assertEqual(manifest["domain"], Path(folder).name)

    def test_bridges_include_usb_reader_and_mango_is_isolated(self):
        modules = {x["slug"]: x for x in mod.module_catalog()}
        core_paths = set(modules["openlvi-bridge"]["paths"])
        mango_paths = set(modules["mango-tuya-local"]["paths"])
        self.assertIn("custom_components/openlvi", core_paths)
        self.assertIn("custom_components/ouman_eh800", core_paths)
        self.assertEqual(mango_paths, {"custom_components/mango_tuya_local"})

    def test_path_traversal_rejected(self):
        for bad in ("../secret", "/etc/passwd", "a/../b", ".env", "a\\b", "a//b"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    mod.safe_relative_path(bad)

    def test_every_zip_contains_only_selected_files(self):
        with tempfile.TemporaryDirectory() as directory:
            for module in mod.module_catalog():
                with self.subTest(slug=module["slug"]):
                    zip_path = Path(directory) / (module["slug"] + ".zip")
                    mod.make_zip(module, zip_path)
                    mod.verify_zip(module, zip_path)
                    with ZipFile(zip_path) as archive:
                        expected = {
                            p.relative_to(ROOT).as_posix()
                            for p in mod.module_files(module)
                        }
                        self.assertEqual(set(archive.namelist()), expected)
                        self.assertFalse(any("ezviz" in name.lower() for name in expected))


if __name__ == "__main__":
    unittest.main()
