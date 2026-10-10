"""Validate stock-APK sources and guard against resurrecting dead download links."""

import unittest
from pathlib import Path

from src.core.config import load_toml, parse_app_entries, parse_config


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config.toml"


class ConfigSourceTests(unittest.TestCase):
    def test_all_enabled_apps_have_supported_download_source(self):
        data = load_toml(CONFIG)
        entries = parse_app_entries(data, parse_config(data))
        enabled = [entry for entry in entries if entry.enabled]
        self.assertTrue(enabled, "Expected at least one enabled app")
        for entry in enabled:
            with self.subTest(app=entry.table):
                self.assertTrue(entry.dl_urls)
                self.assertTrue(set(entry.dl_urls) <= {"apkmirror", "github"})

    def test_removed_upstream_stock_apk_tags_do_not_reappear(self):
        text = CONFIG.read_text(encoding="utf-8")
        self.assertNotIn("nvbangg/builder-for-morphe/releases/tag/", text)
        self.assertNotIn("uptodown-dlurl", text)

    def test_unknown_download_source_is_rejected(self):
        data = {
            "Example": {
                "uptodown-dlurl": "https://example.invalid/android",
                "patches": {"github:example/patches": []},
            }
        }
        with self.assertRaisesRegex(ValueError, "Unsupported download URL key"):
            parse_app_entries(data, parse_config(data))

    def test_enabling_app_without_source_fails_fast(self):
        data = {
            "Example": {
                "enabled": True,
                "patches": {"github:example/patches": []},
            }
        }
        with self.assertRaisesRegex(ValueError, "has no supported APK download source"):
            parse_app_entries(data, parse_config(data))

    def test_disabled_app_without_source_stays_configurable(self):
        data = {
            "Example": {
                "enabled": False,
                "patches": {"github:example/patches": []},
            }
        }
        entries = parse_app_entries(data, parse_config(data))
        self.assertEqual(len(entries), 1)
        self.assertFalse(entries[0].enabled)
        self.assertEqual(entries[0].dl_urls, {})


if __name__ == "__main__":
    unittest.main()
