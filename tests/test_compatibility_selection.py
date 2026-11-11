"""Exercise labelled app versions and variant/group selection used by CI."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

from bs4 import BeautifulSoup

from src.core.patcher import PatcherCLI, _parse_versions_output
from src.scrapers.apkmirror import APKMirrorScraper
from src.scripts.matrix import enabled_brands


def _variant(arch, path, *, code="351011", dpi="nodpi", bundle=True):
    badge = '<span class="apkm-badge">BUNDLE</span>' if bundle else ""
    return f'''<div class="table-row headerFont">
        <div class="table-cell"><a href="{path}">351.11 - Stable</a>{badge}
            <span class="colorLightBlack">{code}</span></div>
        <div class="table-cell">{arch}</div>
        <div class="table-cell">Android 7+</div>
        <div class="table-cell">{dpi}</div>
    </div>'''


class CompatibilitySelectionTests(unittest.TestCase):
    def test_cli_preserves_release_channel_and_selects_architecture_version_code(self):
        output = '''Package name: com.discord
Most common compatible versions:
    351.11 - Stable [versionCodes: ARM64_V8A=351011, ARMEABI_V7A=351012] (79 patches)
    350.8 - Stable (1 patch)

'''
        self.assertEqual(_parse_versions_output(output), ["351.11 - Stable", "350.8 - Stable"])
        cli = PatcherCLI(Path("unused.jar"), {}, Path("unused-signer.jar"))
        with patch.object(cli, "list_versions", return_value=output):
            self.assertEqual(
                cli.get_last_supported_version("", "com.discord", {}, arch="arm64-v8a"),
                ("351.11 - Stable", "351011"),
            )
            self.assertEqual(
                cli.get_last_supported_version("", "com.discord", {}, arch="armeabi-v7a"),
                ("351.11 - Stable", "351012"),
            )

    def test_apkmirror_metadata_preserves_stable_label_and_excludes_beta(self):
        net = Mock()
        net.get.side_effect = [
            '<a href="https://play.google.com/store/apps/details?id=com.discord">Play</a>',
            '''<div id="primary">
                <a class="fontBlack" href="/apk/discord/discord-chat-for-gamers/351-release/">Discord 351.11 - Stable</a>
                <a class="fontBlack" href="/apk/discord/discord-chat-for-gamers/352-release/">Discord 352.2 - Beta</a>
            </div>''',
        ]
        scraper = APKMirrorScraper(net)
        metadata = scraper.fetch_metadata("https://www.apkmirror.com/apk/discord/discord-chat-for-gamers/")
        self.assertEqual(metadata.pkg_name, "com.discord")
        self.assertEqual(metadata.versions, ["351.11 - Stable"])

    def test_variant_version_code_does_not_override_architecture_or_dpi(self):
        markup = (
            _variant("arm64-v8a", "/right")
            + _variant("x86_64", "/wrong-arch")
            + _variant("arm64-v8a", "/wrong-dpi", dpi="480dpi")
        )
        chosen = APKMirrorScraper(Mock())._pick_variant(
            BeautifulSoup(markup, "html.parser"), "nodpi", "arm64-v8a", "351011",
        )
        self.assertEqual(chosen, ("https://www.apkmirror.com/right", "BUNDLE"))

    def test_universal_bundle_satisfies_a_specific_architecture(self):
        markup = _variant("arm64-v8a + armeabi-v7a + x86 + x86_64", "/universal")
        chosen = APKMirrorScraper(Mock())._pick_variant(
            BeautifulSoup(markup, "html.parser"), "", "arm64-v8a", "351011",
        )
        self.assertEqual(chosen, ("https://www.apkmirror.com/universal", "BUNDLE"))

    def test_search_uses_exact_version_not_longer_numeric_prefix(self):
        net = Mock()
        net.get.side_effect = [
            '''<a class="fontBlack" href="/apk/ookla/speedtest/wrong-release/">Speedtest 7.0.40</a>
               <a class="fontBlack" href="/apk/ookla/speedtest/right-release/">Speedtest 7.0.4</a>''',
            '<a class="btn" href="/download-button">Download</a>',
            '<span><a rel="nofollow" href="/stock.apk">Download</a></span>',
        ]
        scraper = APKMirrorScraper(net)
        scraper._category = "speedtest"
        with TemporaryDirectory() as tmp:
            scraper.download("https://www.apkmirror.com/apk/ookla/speedtest/", "7.0.4", Path(tmp) / "stock.apk", "arm64-v8a", "")
        self.assertEqual(net.get.call_args_list[1].args[0],
                         "https://www.apkmirror.com/apk/ookla/speedtest/right-release/")

    def test_requested_publish_groups_are_intersected_with_enabled_entries(self):
        entries = [
            SimpleNamespace(enabled=False, brand="rushi"),
            SimpleNamespace(enabled=False, brand="hooman"),
            SimpleNamespace(enabled=True, brand="Xtra"),
            SimpleNamespace(enabled=True, brand="xtra"),
            SimpleNamespace(enabled=True, brand="venus"),
        ]
        with patch("src.scripts.matrix._load_entries", return_value=entries):
            self.assertEqual(enabled_brands(), ["xtra", "venus"])
            self.assertEqual(enabled_brands(["rushi", "hooman", "VENUS"]), ["venus"])
            self.assertEqual(enabled_brands(["rushi"]), [])


if __name__ == "__main__":
    unittest.main()
