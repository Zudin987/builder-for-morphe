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

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import quote

from src.core.config import TEMP_DIR
from src.core.logger import pr
from src.core.network import NetworkManager

APKSIGNER: Path = Path("bin/apksigner.jar")
_KNOWN_PREFIXES = ("gitlab:", "github:", "forgejo:")


class PrebuiltsError(Exception):
    pass

def _ver_key(ver: str) -> tuple[tuple[int, ...], int, tuple[tuple[int, int | str], ...], str]:
    clean = ver.strip().lstrip("vV")
    match = re.match(r"^(\d+(?:\.\d+)*)(?:[-+](.*))?$", clean)
    if not match:
        nums = tuple(int(x) for x in re.findall(r"\d+", clean)) or (0,)
        return nums, 0, (), clean.lower()

    base = tuple(int(x) for x in match.group(1).split("."))
    prerelease = match.group(2)
    if prerelease is None:
        return base, 1, (), clean.lower()

    tokens: list[tuple[int, int | str]] = []
    for token in re.findall(r"\d+|[A-Za-z]+", prerelease):
        tokens.append((1, int(token)) if token.isdigit() else (0, token.lower()))
    return base, 0, tuple(tokens), clean.lower()

def _strip_src_prefix(src: str) -> str:
    for prefix in _KNOWN_PREFIXES:
        if src.startswith(prefix):
            return src.removeprefix(prefix)
    raise PrebuiltsError(f"Unknown source scheme in {src!r}, expected one of {_KNOWN_PREFIXES}")

def _release_endpoints(src: str) -> tuple[str, str]:
    project = _strip_src_prefix(src)
    if src.startswith("gitlab:"):
        return (
            f"https://gitlab.com/api/v4/projects/{quote(project, safe='')}/releases",
            f"https://gitlab.com/{project}/-/releases",
        )
    if src.startswith("forgejo:"):
        match = re.fullmatch(r"([A-Za-z0-9][A-Za-z0-9.-]*)/([\w.-]+/[\w.-]+)", project, re.ASCII)
        if not match or any(part in {".", ".."} for part in match[2].split("/")):
            raise PrebuiltsError(f"Invalid Forgejo source {src!r}; expected forgejo:host/owner/repo")
        host, repo = match.groups()
        return f"https://{host}/api/v1/repos/{repo}/releases", f"https://{host}/{repo}/releases"
    return f"https://api.github.com/repos/{project}/releases", f"https://github.com/{project}/releases"

def _read_release_json(src: str, url: str, net: NetworkManager) -> dict | list:
    if src.startswith("github:"):
        return json.loads(net.get(url, headers=net._gh_headers))
    return json.loads(net.get(url))

def fetch_latest_release_info(src: str, net: NetworkManager, version: str = "latest") -> tuple[str, str]:
    api_url, _ = _release_endpoints(src)
    if src.startswith("gitlab:"):
        release = _read_release_json(src, f"{api_url}/permalink/latest", net)
        return release.get("description", "") or "", release.get("released_at", "") or ""
    if version == "dev":
        limit = "limit=1" if src.startswith("forgejo:") else "per_page=1"
        releases = _read_release_json(src, f"{api_url}?{limit}", net)
        release = releases[0] if releases else {}
    else:
        release = _read_release_json(src, f"{api_url}/latest", net)
    return release.get("body", "") or "", release.get("published_at", "") or ""

def _prebuilt_directory(src: str) -> Path:
    _release_endpoints(src)
    parts = _strip_src_prefix(src).split("/")
    directory = "-".join(parts[:2]) if src.startswith("forgejo:") else parts[0]
    return TEMP_DIR / directory.lower()

def get_highest_ver(versions: list[str]) -> str:
    clean = [v.strip() for v in versions if v.strip()]
    if not clean:
        raise ValueError("Empty version list")
    return max(clean, key=_ver_key)

def fetch_cli(cli_src: str, cli_ver: str, net: NetworkManager) -> Path:
    cli_dir = _prebuilt_directory(cli_src)
    cli_dir.mkdir(parents=True, exist_ok=True)
    jar, changelog = _fetch_single_asset(cli_src, "CLI", cli_ver, "jar", cli_dir, net)
    if changelog:
        with (cli_dir / "changelog.md").open("a", encoding="utf-8") as f:
            f.write(changelog)
    return jar

def fetch_mpp(src: str, ver: str, net: NetworkManager) -> Path:
    cl_dir = _prebuilt_directory(src)
    cl_dir.mkdir(parents=True, exist_ok=True)
    mpp, changelog = _fetch_single_asset(src, "Patches", ver, "mpp", cl_dir, net)
    if changelog:
        with (cl_dir / "changelog.md").open("a", encoding="utf-8") as f:
            f.write(changelog)
    return mpp

def _get_target_asset(assets: list, ext: str, src: str, ver: str) -> dict:
    suffix = f".{ext}"
    matches: list[dict] = []
    non_dev: list[dict] = []
    for a in assets:
        name = a.get("name", "")
        if not name.endswith(suffix):
            continue
        matches.append(a)
        if "-dev" not in name:
            non_dev.append(a)

    target = non_dev if (len(matches) > 1 and non_dev) else matches
    if not target:
        raise PrebuiltsError(f"No asset (.{ext}) found for {src} @ {ver}")

    if len(target) > 1:
        names = ", ".join(sorted(str(a.get("name", "")) for a in target))
        raise PrebuiltsError(f"Ambiguous assets for {src} @ {ver}: {names}")
    return target[0]

def _verify_digest(file: Path, digest: str | None, src: str, ver: str) -> None:
    if not digest:
        return
    try:
        algorithm, expected = digest.split(":", 1)
    except ValueError as exc:
        raise PrebuiltsError(f"Malformed asset digest for {src} @ {ver}: {digest!r}") from exc
    if algorithm.lower() != "sha256":
        raise PrebuiltsError(f"Unsupported asset digest algorithm for {src} @ {ver}: {algorithm}")

    actual = hashlib.sha256(file.read_bytes()).hexdigest()
    if actual.lower() != expected.lower():
        file.unlink(missing_ok=True)
        raise PrebuiltsError(
            f"SHA-256 mismatch for {src} @ {ver}: expected {expected.lower()}, got {actual.lower()}"
        )

def _build_changelog(tag: str, org: str, name: str, release_url: str) -> str:
    changelog = f"> ⚙️ » {tag}: `{org}/{name}`  \n"
    if tag == "Patches" and release_url:
        changelog += f"[🔗 » Changelog]({release_url})\n\n"
    return changelog

def _fetch_single_asset(src: str, tag: str, ver: str, ext: str, cl_dir: Path, net: NetworkManager) -> tuple[Path, str]:
    gitlab = src.startswith("gitlab:")
    forgejo = src.startswith("forgejo:")
    base_url, web_url = _release_endpoints(src)
    org = _strip_src_prefix(src).split("/")[1 if forgejo else 0]

    release = None
    if ver == "dev":
        releases = _read_release_json(src, base_url, net)
        ver = get_highest_ver([r["tag_name"] for r in releases if r.get("tag_name")])
    elif ver == "latest":
        latest_url = f"{base_url}/permalink/latest" if gitlab else f"{base_url}/latest"
        release = _read_release_json(src, latest_url, net)
        ver = release.get("tag_name", "")

    if release is None:
        lookup_tag = quote(ver, safe="")
        release_url = f"{base_url}/{lookup_tag}" if gitlab else f"{base_url}/tags/{lookup_tag}"
        release = _read_release_json(src, release_url, net)

    raw_assets = release.get("assets", {}).get("links", []) if gitlab else release.get("assets", [])
    asset = _get_target_asset(raw_assets, ext, src, ver)
    tag_name = release.get("tag_name", "")
    encoded_tag = quote(tag_name, safe="")
    if forgejo:
        expected_url = f"{web_url}/download/{encoded_tag}/{quote(asset['name'], safe='')}"
        if (
            not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", tag_name)
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", asset["name"])
            or asset.get("browser_download_url") != expected_url
        ):
            raise PrebuiltsError(f"Unexpected Forgejo asset URL or name for {src} @ {ver}")
        asset_url = expected_url
    else:
        asset_url = (asset.get("direct_asset_url") or asset["url"]) if gitlab else asset["url"]
    release_path = encoded_tag if gitlab else f"tag/{encoded_tag}"
    changelog = _build_changelog(tag, org, asset["name"], f"{web_url}/{release_path}" if tag_name else "")
    file = cl_dir / asset["name"]
    digest = None if gitlab else asset.get("digest")

    if file.exists():
        _verify_digest(file, digest, src, ver)
        return file, changelog

    for old_file in cl_dir.glob(f"*.{ext}"):
        if old_file.is_file() and not old_file.name.startswith("tmp."):
            old_file.unlink(missing_ok=True)

    pr(f"Getting '{asset['name']}' from '{asset_url}'")
    if src.startswith("github:"):
        net.download(asset_url, file, headers=net._gh_headers | {"Accept": "application/octet-stream"})
    else:
        net.download(asset_url, file)
    _verify_digest(file, digest, src, ver)
    return file, changelog

def _find_cached(dir_path: Path, name_ver: str, ext: str) -> Path | None:
    pattern = f"*.{ext}" if name_ver == "*" else f"*{name_ver.lstrip('v')}*.{ext}"
    candidates: list[Path] = []
    for f in dir_path.glob(pattern):
        if not f.is_file() or f.name.startswith("tmp."):
            continue
        candidates.append(f)
    return max(candidates, key=lambda f: _ver_key(f.name), default=None)

def _tag_from_filename(file: Path) -> str:
    m = re.search(r"-(\d[\w.]*)(?:-[^.]+)?\.\w+$", file.name)
    if m:
        return f"v{m.group(1)}"
    return ""
