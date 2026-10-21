#!/usr/bin/env python3
"""Regression tests for the Google/Apple OAuth return into the Capacitor iOS app."""
import plistlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import configure_native_camera_permissions as native


class IOSSocialReturnSchemeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.info_path = Path(self.temp.name) / "Info.plist"
        self.original = {
            "CFBundleName": "A+ Esthetic",
            "CFBundleURLTypes": [{
                "CFBundleURLName": "other.provider",
                "CFBundleURLSchemes": ["other.provider"],
            }],
        }
        with self.info_path.open("wb") as f:
            plistlib.dump(self.original, f)

    def read_info(self):
        with self.info_path.open("rb") as f:
            return plistlib.load(f)

    def test_registers_return_scheme_and_preserves_existing_handlers(self):
        with patch.object(native, "IOS_INFO", self.info_path):
            native.patch_ios()
        info = self.read_info()
        schemes = [s for row in info["CFBundleURLTypes"]
                   for s in row.get("CFBundleURLSchemes", [])]
        self.assertIn("de.aplusesthetic.app", schemes)
        self.assertIn("other.provider", schemes)
        self.assertIn("NSCameraUsageDescription", info)

    def test_sync_patch_is_idempotent(self):
        with patch.object(native, "IOS_INFO", self.info_path):
            native.patch_ios()
            first = self.info_path.read_bytes()
            native.patch_ios()
            second = self.info_path.read_bytes()
        self.assertEqual(first, second)
        info = self.read_info()
        matches = [s for row in info["CFBundleURLTypes"]
                   for s in row.get("CFBundleURLSchemes", [])
                   if s == "de.aplusesthetic.app"]
        self.assertEqual(len(matches), 1)


if __name__ == "__main__":
    unittest.main()
