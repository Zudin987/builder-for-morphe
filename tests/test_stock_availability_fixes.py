"""Regression tests for Brave release fallback and APKMirror stock matching."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock

from bs4 import BeautifulSoup

from src.scrapers.apkmirror import APKMirrorScraper
from src.scrapers.github import GitHubScraper


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
        network = Mock()
        network._gh_headers = {}
        network.get.return_value = """{
            "name": "Release v1.98.60",
            "assets": [
                {"name":"BraveMonoarm64.apk", "browser_download_url":"https://example.invalid/BraveMonoarm64.apk"},
                {"name":"BraveMonoarm.apk", "browser_download_url":"https://example.invalid/BraveMonoarm.apk"}
            ]
        }"""
        scraper = GitHubScraper(network)
        with TemporaryDirectory() as tmp:
            dest = Path(tmp) / "stock.apk"
            result = scraper.download(
                "https://github.com/brave/brave-browser/releases/tag/v{version}",
                "1.98.60", dest, "arm64-v8a", "",
            )
            self.assertEqual(result.path, dest)
            self.assertFalse(result.is_bundle)
            network.get.assert_called_once()
            self.assertEqual(network.get.call_args.args[0], "https://api.github.com/repos/brave/brave-browser/releases/tags/v1.98.60")
            self.assertEqual(network.download.call_args.args[0], "https://example.invalid/BraveMonoarm64.apk")

    def test_brave_does_not_use_official_mapping_for_untrusted_repo(self):
        network = Mock()
        network._gh_headers = {}
        network.get.return_value = """{"name":"v1.98.60","assets":[
            {"name":"BraveMonoarm64.apk","browser_download_url":"https://example.invalid/wrong.apk"}
        ]}"""
        scraper = GitHubScraper(network)
        from src.scrapers.github import GitHubReleasesError
        with TemporaryDirectory() as tmp, self.assertRaises(GitHubReleasesError):
            scraper.download("https://github.com/untrusted/other/releases/tag/v{version}",
                             "1.98.60", Path(tmp) / "stock.apk", "arm64-v8a", "")


if __name__ == "__main__":
    unittest.main()
