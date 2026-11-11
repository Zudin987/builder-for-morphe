# ---------------------------------------------------------
# Copyright (C) 2026 krvstek (Original Author)
# Copyright (C) 2026 The uni-apks Contributors (Modifications)
# 
# DO NOT REMOVE OR ALTER THIS COPYRIGHT HEADER.
# This file is part of uni-apks.
# Canonical source: https://github.com/krvstek/uni-apks
#
# Licensed under the GNU GPLv3. You may modify this file,
# but you MUST keep this original copyright notice intact
# and prominently state any changes made.
# See the AUTHORS file in the root directory for details.
# ---------------------------------------------------------

import re  # noqa: I001
from pathlib import Path
from urllib.parse import urlencode, urljoin

from bs4 import BeautifulSoup

from src.core.network import NetworkManager, ResourceNotFoundError
from src.scrapers.base import AppMetadata, BaseScraper, DownloadResult, ScraperError, _parse_html

_DEFAULT_ARCH: frozenset[str] = frozenset({"universal", "noarch", "arm64-v8a + armeabi-v7a", "arm64-v8a + armeabi"})


def _release_version(title: str) -> str | None:
    # Preserve display labels required by some patch bundles, rather than
    # treating the last word ("Stable") as the version.
    match = re.search(r"\b(\d[\w.+-]*(?:\s+-\s+Stable)?)$", title.strip(), re.IGNORECASE)
    return match.group(1) if match else None

class APKMirrorError(ScraperError):
    pass

class APKMirrorScraper(BaseScraper):
    def __init__(self, net: NetworkManager) -> None:
        super().__init__(net)
        self._category: str = ""
        self._release_urls: dict[str, str] = {}

    def fetch_metadata(self, url: str) -> AppMetadata:
        resp_html = self.net.get(url)
        self._category = url.rstrip("/").split("/")[-1]
        m = re.search(r"play\.google\.com/store/apps/details\?id=([\w.]+)", resp_html)
        if not m:
            raise APKMirrorError("Package name not found")

        soup = _parse_html(self.net.get(f"https://www.apkmirror.com/uploads/?appcategory={self._category}"))
        versions: list[str] = []
        for a in soup.select("#primary a.fontBlack[href*='-release/']"):
            text = a.get_text(" ", strip=True)
            if "beta" in text.lower() or "alpha" in text.lower() or "secondary" in text.lower():
                continue
            v = _release_version(text)
            if v is None:
                continue
            self._release_urls[v] = urljoin("https://www.apkmirror.com", a["href"])
            versions.append(v)
        return AppMetadata(pkg_name=m.group(1), versions=versions)

    def download(self, url: str, version: str, dest: Path, arch: str, dpi: str, version_code: str | None = None) -> DownloadResult:
        release_url = self._release_urls.get(version)
        if release_url is None:
            search_html = self.net.get(f"{url.rstrip('/')}/?{urlencode({'s': version})}")
            soup = _parse_html(search_html)
            for a in soup.select("a.fontBlack[href*='-release/']"):
                text = a.get_text(" ", strip=True)
                if _release_version(text) == version and f"/{self._category}/" in a.get("href", ""):
                    if "secondary" in text.lower() and "secondary" not in version.lower():
                        continue
                    release_url = urljoin("https://www.apkmirror.com", a["href"])
                    break

        if release_url is None:
            raise APKMirrorError("Version not found")

        try:
            release_html = self.net.get(release_url)
        except ResourceNotFoundError:
            raise APKMirrorError("Version not found") from None

        is_bundle = False
        soup_release = _parse_html(release_html)
        if soup_release.select_one("div.table-row.headerFont:last-child"):
            dl_url = self._pick_variant(soup_release, dpi, arch, version_code=version_code)
            if dl_url is None:
                raise APKMirrorError("No matching variant found")
            release_html = self.net.get(dl_url[0])
            is_bundle = dl_url[1] == "BUNDLE"

        soup_dl = _parse_html(release_html)
        btn = soup_dl.select_one("a.btn[href]")
        if btn is None:
            raise APKMirrorError("Download button not found; APKMirror page layout may have changed")
        btn_url = urljoin("https://www.apkmirror.com", str(btn["href"]))

        soup_final = _parse_html(self.net.get(btn_url))
        dl_link = soup_final.select_one("span > a[rel=nofollow][href]")
        if dl_link is None:
            raise APKMirrorError("Final download link not found; APKMirror page layout may have changed")
        final_url = urljoin("https://www.apkmirror.com", str(dl_link["href"]))

        out_path = dest.with_suffix(".apkm") if is_bundle else dest
        self.net.download(final_url, out_path)
        return DownloadResult(path=out_path, is_bundle=is_bundle)

    def _pick_variant(self, soup: BeautifulSoup, dpi: str, arch: str, version_code: str | None = None) -> tuple[str, str] | None:
        rows = soup.select("div.table-row.headerFont")
        for bundle_type in ("APK", "BUNDLE"):
            for row in reversed(rows):
                cells = row.select("div.table-cell")
                if len(cells) < 4:
                    continue

                link = cells[0].select_one("a")
                if not link or not link.get("href"):
                    continue

                badge = cells[0].select_one(".apkm-badge")
                b_type = badge.get_text(strip=True).upper() if badge else "APK"

                extracted_vcode = None
                for span in cells[0].select("span.colorLightBlack"):
                    if "wrapText" not in span.get("class", []) and not span.select_one(".dateyear_utc"):
                        txt = span.get_text(strip=True)
                        if txt.isdigit():
                            extracted_vcode = txt
                            break

                arch_text = cells[1].get_text(strip=True)
                row_arches = set(re.findall(r"[\w-]+", arch_text.lower()))
                arch_ok = bool({"universal", "noarch"} & row_arches) or (
                    arch != "all" and arch in row_arches
                ) or (
                    arch == "all" and (
                        arch_text in _DEFAULT_ARCH or {"arm64-v8a", "armeabi-v7a"} <= row_arches
                    )
                )
                dpi_text = cells[3].get_text(strip=True)
                dpi_ok = not dpi or not dpi_text or re.match(r"\d+-640dpi", dpi_text) or dpi_text in {"nodpi", "anydpi"} or dpi_text == dpi
                code_ok = version_code is None or extracted_vcode == version_code
                if b_type == bundle_type and arch_ok and dpi_ok and code_ok:
                    return urljoin("https://www.apkmirror.com", str(link["href"])), bundle_type
        return None
