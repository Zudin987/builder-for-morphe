from __future__ import annotations

import contextlib
import json
import os
import re
import sys
from pathlib import Path

from src.core.builder import _find_pkg_name, _make_scraper, _resolve_version
from src.core.config import CONFIG_PATH, TEMP_DIR, load_toml, parse_app_entries, parse_config
from src.core.network import NetworkManager
from src.core.patcher import PatcherCLI
from src.core.prebuilts import APKSIGNER, fetch_cli, fetch_mpp


WATCHED_VERSIONS = {"auto", "latest", "exp"}


def _normalize_version(version: str) -> str:
    return version.replace(" ", "").lstrip("v")


def _asset_prefix(app_name: str, brand: str) -> str:
    base = f"{app_name.lower().replace(' ', '-')}-{brand.lower().replace(' ', '-')}"
    return re.sub(r"\.+", ".", re.sub(r"[^a-zA-Z0-9@+\-_.]", ".", base))


def _expected_arches(arch: str) -> tuple[str, ...]:
    return ("arm64-v8a", "armeabi-v7a") if arch == "both" else (arch,)


def _published_asset_names(repo: str, net: NetworkManager) -> list[str]:
    raw = net.get(
        f"https://api.github.com/repos/{repo}/releases?per_page=100",
        headers=net._gh_headers,
    )
    releases = json.loads(raw)
    names: list[str] = []
    for release in releases:
        if release.get("draft"):
            continue
        names.extend(asset.get("name", "") for asset in release.get("assets", []))
    return names


def _built_version(asset_names: list[str], app_name: str, brand: str, arch: str) -> str | None:
    prefix = re.escape(_asset_prefix(app_name, brand))
    suffix = re.escape(arch)
    pattern = re.compile(rf"^{prefix}-v(.+)-{suffix}\.apk$", re.IGNORECASE)
    for name in asset_names:
        match = pattern.match(name)
        if match:
            return _normalize_version(match.group(1))
    return None


def main() -> int:
    repo = os.getenv("GITHUB_REPOSITORY", "").strip()
    if not repo:
        print("[]")
        return 0

    excluded = {
        item.strip()
        for item in os.getenv("APP_UPDATE_WATCH_EXCLUDE", "").split(",")
        if item.strip()
    }

    data = load_toml(CONFIG_PATH)
    main_cfg = parse_config(data)
    entries = [
        entry
        for entry in parse_app_entries(data, main_cfg)
        if entry.enabled
        and entry.table not in excluded
        and entry.version in WATCHED_VERSIONS
        and entry.dl_urls
        and entry.patches
    ]

    if not entries:
        print("[]")
        return 0

    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    brands_to_build: set[str] = set()
    release_lookup_failed = False

    # Upstream helpers print progress to stdout. Redirect that progress to stderr
    # so stdout remains exactly one JSON array for the workflow to consume.
    with contextlib.redirect_stdout(sys.stderr):
        with NetworkManager() as net:
            try:
                asset_names = _published_asset_names(repo, net)
            except Exception as exc:
                print(f"App-version watcher: could not read our releases: {exc}", file=sys.stderr)
                release_lookup_failed = True
                asset_names = []

            if not release_lookup_failed:
                cli_cache: dict[tuple[str, str], Path] = {}
                mpp_cache: dict[tuple[str, str], Path] = {}

                for entry in entries:
                    try:
                        scrapers = {source: _make_scraper(source, net) for source in entry.dl_urls}
                        pkg_name, dl_from, _ = _find_pkg_name(entry, scrapers)

                        cli_key = (entry.cli_source, entry.cli_version)
                        if cli_key not in cli_cache:
                            cli_cache[cli_key] = fetch_cli(entry.cli_source, entry.cli_version, net)

                        app_mpp_map: dict[tuple[str, str], Path] = {}
                        for source, spec in entry.patches.items():
                            key = (source, spec["version"])
                            if key not in mpp_cache:
                                mpp_cache[key] = fetch_mpp(source, spec["version"], net)
                            app_mpp_map[key] = mpp_cache[key]

                        patcher = PatcherCLI(cli_cache[cli_key], app_mpp_map, APKSIGNER)
                        list_patches = patcher.list_patches(
                            pkg_name,
                            experimental=entry.version == "exp",
                        )
                        target_version, _ = _resolve_version(
                            entry,
                            patcher,
                            list_patches,
                            pkg_name,
                            dl_from,
                            scrapers,
                        )
                        target = _normalize_version(target_version)

                        needs_build = False
                        old_versions: list[str] = []
                        for arch in _expected_arches(entry.arch):
                            built = _built_version(asset_names, entry.app_name, entry.brand, arch)
                            old_versions.append(built or "missing")
                            if built != target:
                                needs_build = True

                        if needs_build:
                            brands_to_build.add(entry.brand.lower())
                            print(
                                f"App-version watcher: {entry.table} target={target} built={','.join(old_versions)} -> rebuild {entry.brand.lower()}",
                                file=sys.stderr,
                            )
                    except Exception as exc:
                        # This watcher is an enhancement only. The upstream patch-release
                        # checker must keep working even if one app source temporarily fails.
                        print(
                            f"App-version watcher: skipped {entry.table}: {exc}",
                            file=sys.stderr,
                        )

    print("[]" if release_lookup_failed else json.dumps(sorted(brands_to_build)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
