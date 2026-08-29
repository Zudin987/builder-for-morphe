from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.core.config import AppEntry, parse_app_entries, parse_config
from src.core.prebuilts import PrebuiltsError, _get_target_asset, _verify_digest, get_highest_ver
from src.scrapers.apkmirror import APKMirrorError, APKMirrorScraper
from src.scripts.matrix import _fetch_our_releases


ROOT = Path(__file__).resolve().parents[1]
WATCHER_PATH = ROOT / ".github" / "scripts" / "check_app_updates.py"
_spec = importlib.util.spec_from_file_location("check_app_updates", WATCHER_PATH)
assert _spec and _spec.loader
watcher = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(watcher)


def _entry(*, arch: str = "both") -> AppEntry:
    return AppEntry(
        table="Example",
        app_name="Example",
        brand="morphe",
        arch=arch,
        dpi="",
        version="auto",
        dl_urls={"apkmirror": "https://example.invalid"},
        patcher_args=[],
        patches={"github:example/patches": {"version": "latest", "include": [], "exclude": []}},
        exclusive_patches=False,
        cli_source="github:example/cli",
        cli_version="latest",
        skip_sigcheck=False,
        enabled=True,
        changelog_keywords=[],
    )


class FakeNet:
    def __init__(self, payload):
        self.payload = payload
        self._gh_headers = {}

    def get(self, *_args, **_kwargs):
        return json.dumps(self.payload) if not isinstance(self.payload, str) else self.payload


class HardeningTests(unittest.TestCase):
    def test_watcher_resolves_both_architectures(self):
        seen: list[str] = []

        def fake_resolve(*args, **kwargs):
            arch = args[-1]
            seen.append(arch)
            return ("1.2.3", None, False)

        with patch.object(watcher, "_resolve_version", side_effect=fake_resolve):
            targets = watcher._resolve_targets(_entry(), object(), "patches", "pkg", "apkmirror", {})

        self.assertEqual(seen, ["arm64-v8a", "armeabi-v7a"])
        self.assertEqual(targets, {"arm64-v8a": "1.2.3", "armeabi-v7a": "1.2.3"})

    def test_watcher_uses_only_published_release_assets(self):
        releases = [
            {"draft": True, "prerelease": False, "assets": [{"name": "example-morphe-v1.2.3-all.apk"}]},
            {"draft": False, "prerelease": True, "assets": [{"name": "example-morphe-v1.2.4-all.apk"}]},
            {"draft": False, "prerelease": False, "assets": [{"name": "example-morphe-v1.2.5-all.apk"}]},
        ]
        names = watcher._release_asset_names("owner/repo", FakeNet(releases))
        self.assertEqual(names, ["example-morphe-v1.2.5-all.apk"])

    def test_watcher_treats_builder_discovery_errors_as_transient_only(self):
        self.assertIn(watcher.BuilderError, watcher._EXPECTED_TRANSIENT_ERRORS)
        self.assertNotIn(TypeError, watcher._EXPECTED_TRANSIENT_ERRORS)
        self.assertNotIn(AttributeError, watcher._EXPECTED_TRANSIENT_ERRORS)

    def test_matrix_uses_successful_draft_timestamp(self):
        releases = [
            {
                "tag_name": "26.08.29-morphe",
                "draft": True,
                "published_at": None,
                "updated_at": "2026-08-29T12:00:00+00:00",
                "created_at": "2026-08-29T11:00:00+00:00",
                "assets": [{"name": "example-morphe-v1.2.3-all.apk"}],
            }
        ]
        state = _fetch_our_releases("owner/repo", FakeNet(releases))
        self.assertEqual(state["morphe"], "2026-08-29T12:00:00+00:00")

    def test_prerelease_numeric_version_ordering(self):
        self.assertEqual(get_highest_ver(["v1.20.0-dev.2", "v1.20.0-dev.10"]), "v1.20.0-dev.10")
        self.assertEqual(get_highest_ver(["v1.20.0-dev.99", "v1.20.0"]), "v1.20.0")

    def test_digest_verification_accepts_match_and_rejects_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "asset.jar"
            path.write_bytes(b"trusted")
            digest = hashlib.sha256(b"trusted").hexdigest()
            _verify_digest(path, f"sha256:{digest}", "github:example/repo", "v1")
            self.assertTrue(path.exists())

            with self.assertRaises(PrebuiltsError):
                _verify_digest(path, "sha256:" + "0" * 64, "github:example/repo", "v1")
            self.assertFalse(path.exists())

    def test_ambiguous_patch_assets_are_rejected(self):
        assets = [{"name": "patches-one.mpp"}, {"name": "patches-two.mpp"}]
        with self.assertRaisesRegex(PrebuiltsError, "Ambiguous assets"):
            _get_target_asset(assets, "mpp", "github:example/patches", "v1")

    def test_ci_forces_strict_signature_checking(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}, clear=False):
            cfg = parse_config({"strict-sigcheck": False})
        self.assertTrue(cfg.strict_sigcheck)

    def test_ci_signature_exceptions_are_explicit_and_narrow(self):
        data = {
            "Brave": {
                "enabled": True,
                "apkmirror-dlurl": "https://example.invalid/brave",
                "patches": {"github:example/patches": []},
            },
            "Backdrops": {
                "enabled": True,
                "apkmirror-dlurl": "https://example.invalid/backdrops",
                "patches": {"github:example/patches": []},
            },
            "YouTube": {
                "enabled": True,
                "apkmirror-dlurl": "https://example.invalid/youtube",
                "patches": {"github:example/patches": []},
            },
        }
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}, clear=False):
            cfg = parse_config(data)
            entries = {entry.table: entry for entry in parse_app_entries(data, cfg)}

        self.assertTrue(entries["Brave"].skip_sigcheck)
        self.assertTrue(entries["Backdrops"].skip_sigcheck)
        self.assertFalse(entries["YouTube"].skip_sigcheck)

    def test_apkmirror_missing_button_is_scraper_error(self):
        scraper = APKMirrorScraper(FakeNet("<html><body>layout changed</body></html>"))
        scraper._release_urls["1.0"] = "https://www.apkmirror.com/apk/example/example-release/"
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(APKMirrorError, "Download button not found"):
                scraper.download(
                    "https://www.apkmirror.com/apk/example/example",
                    "1.0",
                    Path(tmp) / "stock.apk",
                    "all",
                    "",
                )


if __name__ == "__main__":
    unittest.main()
