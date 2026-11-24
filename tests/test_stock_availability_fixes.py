"""Regression tests for stock APK availability and official Brave asset integrity."""

import contextlib
import hashlib
import io
import json
import os
import subprocess
import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from bs4 import BeautifulSoup

from src.core.builder import BuildExit, _download_apk, _find_pkg_name, _resolve_version, run_build
from src.core.config import load_toml, parse_app_entries, parse_config
from src.core.logger import epr
from src.core.network import NetworkError
from src.core.patcher import PatcherError
from src.scrapers.apkmirror import APKMirrorScraper
from src.scrapers.base import AppMetadata, DownloadResult, StockUnavailableError
from src.scrapers.github import GitHubReleasesError, GitHubScraper


BRAVE_FIXTURE = b"official brave APK test fixture"


def _brave_network(*, payload=BRAVE_FIXTURE, digest=None, url=None):
    network = Mock()
    network._gh_headers = {}
    if digest is None:
        digest = "sha256:" + hashlib.sha256(BRAVE_FIXTURE).hexdigest()
    if url is None:
        url = "https://github.com/brave/brave-browser/releases/download/v1.98.60/BraveMonoarm64.apk"
    network.get.return_value = json.dumps({
        "name": "Release v1.98.60",
        "tag_name": "v1.98.60",
        "assets": [
            {"name": "BraveMonoarm64.apk", "digest": digest, "browser_download_url": url},
            {"name": "BraveMonoarm.apk", "browser_download_url": "https://example.invalid/BraveMonoarm.apk"},
        ],
    })

    def download(_url, dest, **_kwargs):
        dest.write_bytes(payload)

    network.download.side_effect = download
    return network


class StockAvailabilityFixTests(unittest.TestCase):
    def test_brave_discovery_and_download_use_patch_required_official_release(self):
        data = load_toml(Path(__file__).resolve().parents[1] / "config.toml")
        brave = next(e for e in parse_app_entries(data, parse_config(data)) if e.table == "Brave")
        network = _brave_network()
        target_release = json.loads(network.get.return_value)
        latest_release = {
            "name": "Brave Release v1.99.1",
            "tag_name": "v1.99.1",
            "assets": [{"name": "BraveMonoarm64.apk", "browser_download_url": "https://example.invalid/latest.apk"}],
        }
        network.get.side_effect = lambda url, **_kwargs: json.dumps(
            latest_release if url.endswith("/releases/latest") else target_release
        )
        scrapers = {"github": GitHubScraper(network)}
        patcher = Mock()
        patcher.get_last_supported_version.return_value = ("1.98.60", None)
        with TemporaryDirectory() as tmp, patch("src.core.builder.TEMP_DIR", Path(tmp)):
            pkg_name, source, failed = _find_pkg_name(brave, scrapers)
            self.assertEqual(pkg_name, "com.brave.browser")
            self.assertEqual(source, "github")
            self.assertEqual(failed, {})
            version, vcode, force = _resolve_version(
                brave, patcher, "patches", pkg_name, source, scrapers, brave.arch,
            )
            self.assertEqual(version, "1.98.60")
            self.assertFalse(force)
            result = _download_apk(
                brave, version, brave.arch, pkg_name, scrapers, source, failed, vcode,
            )
            self.assertFalse(result.is_bundle)
            self.assertEqual(result.path.read_bytes(), BRAVE_FIXTURE)

        self.assertEqual([call.args[0] for call in network.get.call_args_list], [
            "https://api.github.com/repos/brave/brave-browser/releases/latest",
            "https://api.github.com/repos/brave/brave-browser/releases/tags/v1.98.60",
        ])
        self.assertEqual(
            network.download.call_args.args[0],
            "https://github.com/brave/brave-browser/releases/download/v1.98.60/BraveMonoarm64.apk",
        )

    def test_brave_metadata_uses_package_name_and_release_tag(self):
        network = Mock()
        network._gh_headers = {}
        network.get.return_value = json.dumps({
            "name": "Brave Release v1.98.63 (Chromium build)",
            "tag_name": "v1.98.63",
            "assets": [],
        })
        metadata = GitHubScraper(network).fetch_metadata(
            "https://github.com/brave/brave-browser/releases/tag/v{version}",
        )
        self.assertEqual(metadata.pkg_name, "com.brave.browser")
        self.assertEqual(metadata.versions, ["1.98.63"])
        self.assertEqual(network.get.call_args.args[0],
                         "https://api.github.com/repos/brave/brave-browser/releases/latest")

    def test_brave_download_refreshes_assets_when_target_version_changes(self):
        network = _brave_network()
        first_release = json.loads(network.get.return_value)
        next_release = json.loads(network.get.return_value.replace("1.98.60", "1.98.63"))
        network.get.side_effect = [json.dumps(first_release), json.dumps(next_release)]
        scraper = GitHubScraper(network)
        with TemporaryDirectory() as tmp:
            for version in ("1.98.60", "1.98.63"):
                scraper.download(
                    "https://github.com/brave/brave-browser/releases/tag/v{version}",
                    version, Path(tmp) / f"{version}.apk", "arm64-v8a", "",
                )
        self.assertEqual(network.get.call_count, 2)
        self.assertEqual(network.download.call_args.args[0],
                         "https://github.com/brave/brave-browser/releases/download/v1.98.63/BraveMonoarm64.apk")

    def test_apkmirror_allows_dpi_when_unspecified(self):
        markup = """
        <div class="table-row headerFont">
            <div class="table-cell"><a href="/apk/reddit/test-apk">APK</a></div>
            <div class="table-cell">universal</div>
            <div class="table-cell">Android</div>
            <div class="table-cell">320dpi</div>
        </div>
        """
        scraper = APKMirrorScraper(Mock())
        chosen = scraper._pick_variant(BeautifulSoup(markup, "html.parser"), "", "all")
        self.assertEqual(chosen, ("https://www.apkmirror.com/apk/reddit/test-apk", "APK"))

    def test_brave_official_release_asset_without_version_in_name(self):
        network = _brave_network()
        scraper = GitHubScraper(network)
        with TemporaryDirectory() as tmp:
            dest = Path(tmp) / "stock.apk"
            result = scraper.download(
                "https://github.com/brave/brave-browser/releases/tag/v{version}",
                "1.98.60", dest, "arm64-v8a", "",
            )
            self.assertEqual(result.path, dest)
            self.assertFalse(result.is_bundle)
            self.assertEqual(dest.read_bytes(), BRAVE_FIXTURE)
            network.get.assert_called_once()
            self.assertEqual(
                network.get.call_args.args[0],
                "https://api.github.com/repos/brave/brave-browser/releases/tags/v1.98.60",
            )
            self.assertEqual(
                network.download.call_args.args[0],
                "https://github.com/brave/brave-browser/releases/download/v1.98.60/BraveMonoarm64.apk",
            )

    def test_brave_rejects_changed_apk_and_deletes_it(self):
        network = _brave_network(payload=b"tampered bytes")
        scraper = GitHubScraper(network)
        with TemporaryDirectory() as tmp:
            dest = Path(tmp) / "stock.apk"
            with self.assertRaisesRegex(GitHubReleasesError, "digest mismatch"):
                scraper.download(
                    "https://github.com/brave/brave-browser/releases/tag/v{version}",
                    "1.98.60", dest, "arm64-v8a", "",
                )
            self.assertFalse(dest.exists())

    def test_brave_requires_release_digest(self):
        network = _brave_network(digest="invalid")
        scraper = GitHubScraper(network)
        with TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(GitHubReleasesError, "no valid SHA-256 digest"):
                scraper.download(
                    "https://github.com/brave/brave-browser/releases/tag/v{version}",
                    "1.98.60", Path(tmp) / "stock.apk", "arm64-v8a", "",
                )
        network.download.assert_not_called()

    def test_brave_requires_official_asset_url(self):
        network = _brave_network(url="https://example.invalid/fake.apk")
        scraper = GitHubScraper(network)
        with TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(GitHubReleasesError, "not trusted"):
                scraper.download(
                    "https://github.com/brave/brave-browser/releases/tag/v{version}",
                    "1.98.60", Path(tmp) / "stock.apk", "arm64-v8a", "",
                )
        network.download.assert_not_called()

    def test_brave_does_not_use_official_mapping_for_untrusted_repo(self):
        network = Mock()
        network._gh_headers = {}
        network.get.return_value = """{"name":"v1.98.60","assets":[
            {"name":"BraveMonoarm64.apk","browser_download_url":"https://example.invalid/wrong.apk"}
        ]}"""
        scraper = GitHubScraper(network)
        with TemporaryDirectory() as tmp, self.assertRaises(StockUnavailableError):
            scraper.download(
                "https://github.com/untrusted/other/releases/tag/v{version}",
                "1.98.60", Path(tmp) / "stock.apk", "arm64-v8a", "",
            )

    def test_ci_solver_starts_before_update_watcher(self):
        workflow = (
            Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"
        ).read_text(encoding="utf-8")
        self.assertLess(
            workflow.index("Start Cloudflare challenge solver for version checks"),
            workflow.index("- name: Get build matrix"),
        )
        self.assertIn("http://127.0.0.1:8000/docs", workflow)
        self.assertIn("refusing an incomplete app-version check", workflow)

    def test_build_exit_distinguishes_stock_outage_from_patching_and_integrity(self):
        data = load_toml(Path("config.toml"))
        config = replace(parse_config(data), parallel_jobs=1)
        facebook = next(entry for entry in parse_app_entries(data, config) if entry.table == "Facebook")
        stock = DownloadResult(Path("stock.apkm"), is_bundle=True)

        def recovered_download(*args, **kwargs):
            epr("JS challenge detected for APKMirror, attempting solver bypass")
            return stock

        for download, patch_failure, expected in (
            (NetworkError("Request failed after 3 attempts"), None, BuildExit.STOCK_UNAVAILABLE),
            (StockUnavailableError("No matching variant found"), None, BuildExit.STOCK_UNAVAILABLE),
            (GitHubReleasesError("Official Brave APK SHA-256 digest mismatch"), None, BuildExit.FAILED),
            (recovered_download, PatcherError('Patch "AMOLED dark theme" failed'), BuildExit.FAILED),
        ):
            with self.subTest(download=download, patch_failure=patch_failure):
                scraper = Mock()
                scraper.cached_metadata.return_value = AppMetadata("com.facebook.katana", ["580.0.0.51.74"])
                scraper.download.side_effect = download
                with (
                    TemporaryDirectory() as temp,
                    contextlib.redirect_stderr(io.StringIO()),
                    patch("src.core.builder.TEMP_DIR", Path(temp)),
                    patch("src.core.builder._make_scraper", return_value=scraper),
                    patch("src.core.builder.fetch_cli"),
                    patch("src.core.builder.fetch_mpp"),
                    patch("src.core.builder.PatcherCLI") as patcher,
                    patch("src.core.builder._verify_sig"),
                    patch("src.core.builder._apply_patch", side_effect=patch_failure) as apply_patch,
                ):
                    patcher.return_value.get_last_supported_version.return_value = ("580.0.0.51.74", None)
                    self.assertEqual(run_build([facebook], config, Mock()), expected)
                self.assertEqual(apply_patch.call_count, int(patch_failure is not None))

    def test_ci_shell_retries_only_the_stock_unavailable_status(self):
        script = Path(__file__).resolve().parents[1] / ".github/scripts/run_build_resilient.sh"
        with TemporaryDirectory() as temp:
            uv = Path(temp) / "uv"
            uv.write_text(
                '#!/usr/bin/env bash\necho "JS challenge detected"\nexit "$TEST_BUILD_STATUS"\n',
                encoding="utf-8",
            )
            uv.chmod(0o755)
            for status, tolerate, expected, attempts in (
                (BuildExit.FAILED, "true", BuildExit.FAILED, 1),
                (BuildExit.STOCK_UNAVAILABLE, "true", BuildExit.SUCCESS, 2),
                (BuildExit.STOCK_UNAVAILABLE, "false", BuildExit.STOCK_UNAVAILABLE, 2),
            ):
                with self.subTest(status=status, tolerate=tolerate):
                    result = subprocess.run(
                        ["bash", str(script), "Facebook", "armeabi-v7a"],
                        capture_output=True,
                        text=True,
                        env={
                            **os.environ,
                            "PATH": f"{temp}:{os.environ['PATH']}",
                            "TEST_BUILD_STATUS": str(status),
                            "TOLERATE_STOCK_UNAVAILABLE": tolerate,
                            "BUILD_RETRY_DELAY": "0",
                            "BUILD_ATTEMPTS": "2",
                        },
                    )
                    self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
                    self.assertEqual(result.stdout.count("Build attempt"), attempts)

    def test_facebook_config_targets_the_supported_arm64_variant(self):
        data = load_toml(Path("config.toml"))
        facebook = next(entry for entry in parse_app_entries(data, parse_config(data)) if entry.table == "Facebook")
        source = "github:RookieEnough/De-Vanced"
        self.assertTrue(facebook.enabled)
        self.assertEqual(facebook.arch, "arm64-v8a")
        self.assertEqual(facebook.patches[source]["exclude"], [])


if __name__ == "__main__":
    unittest.main()
