"""Regression tests for stock APK availability and official Brave asset integrity."""

import hashlib
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock

from bs4 import BeautifulSoup

from src.scrapers.apkmirror import APKMirrorScraper
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
        with TemporaryDirectory() as tmp, self.assertRaises(GitHubReleasesError):
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


if __name__ == "__main__":
    unittest.main()
