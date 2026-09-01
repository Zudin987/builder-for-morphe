from __future__ import annotations

import json
import os
from datetime import datetime

from src.core.config import CONFIG_PATH, load_toml, parse_app_entries, parse_config
from src.core.logger import epr
from src.core.network import NetworkManager, ResourceNotFoundError

MAX_RELEASE_PAGES = 5


def _fetch_latest_patch_release(source: str, net: NetworkManager, version: str = "latest") -> tuple[str, str]:
    scheme, clean_src = source.split(":", 1)
    if scheme == "gitlab":
        project = clean_src.replace("/", "%2F")
        upstream_rel = json.loads(
            net.get(f"https://gitlab.com/api/v4/projects/{project}/releases/permalink/latest")
        )
        return upstream_rel.get("description", "") or "", upstream_rel.get("released_at", "") or ""

    if version == "dev":
        releases = json.loads(
            net.get(
                f"https://api.github.com/repos/{clean_src}/releases?per_page=1",
                headers=net._gh_headers,
            )
        )
        upstream_rel = releases[0] if releases else {}
    else:
        upstream_rel = json.loads(
            net.get(
                f"https://api.github.com/repos/{clean_src}/releases/latest",
                headers=net._gh_headers,
            )
        )

    return upstream_rel.get("body", "") or "", upstream_rel.get("published_at", "") or ""


def _parse_date(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _fetch_published_builds(repo: str, net: NetworkManager) -> dict[str, str]:
    """Return the newest Obtainium-visible successful build timestamp per brand.

    Drafts and prereleases are intentionally ignored. A daily build should only use a
    release as its patch baseline if normal Obtainium clients can see that release.
    We also choose the newest timestamp explicitly instead of trusting GitHub API order.
    """
    newest_by_brand: dict[str, str] = {}

    for page in range(1, MAX_RELEASE_PAGES + 1):
        try:
            raw = net.get(
                f"https://api.github.com/repos/{repo}/releases?per_page=100&page={page}",
                headers=net._gh_headers,
            )
            releases = json.loads(raw)
        except Exception as exc:
            epr(f"Failed to fetch published build baseline page {page}: {exc}")
            break

        if not isinstance(releases, list) or not releases:
            break

        for rel in releases:
            if rel.get("draft") or rel.get("prerelease"):
                continue
            if not any(asset.get("name", "").endswith(".apk") for asset in rel.get("assets", [])):
                continue

            published_at = rel.get("published_at") or ""
            tag = rel.get("tag_name", "")
            brand = tag.split("-", 1)[1] if "-" in tag else ""
            if not brand or not published_at:
                continue

            previous = newest_by_brand.get(brand)
            if previous is None or _parse_date(published_at) > _parse_date(previous):
                newest_by_brand[brand] = published_at

        if len(releases) < 100:
            break

    return newest_by_brand


def _load_entries() -> list:
    data = load_toml(CONFIG_PATH)
    return parse_app_entries(data, parse_config(data))


def main() -> None:
    repo = os.getenv("GITHUB_REPOSITORY")
    if not repo:
        raise RuntimeError("GITHUB_REPOSITORY environment variable is not set")

    entries = [entry for entry in _load_entries() if entry.enabled]
    patches_by_brand: dict[str, str] = {}
    entries_by_brand: dict[str, list] = {}
    dev_brands: set[str] = set()

    for entry in entries:
        brand = entry.brand.lower()
        entries_by_brand.setdefault(brand, []).append(entry)
        if brand not in patches_by_brand:
            patches_by_brand[brand] = next(iter(entry.patches), "")
        if any(spec["version"] == "dev" for spec in entry.patches.values()):
            dev_brands.add(brand)

    with NetworkManager() as net:
        published_builds = _fetch_published_builds(repo, net)
        brands_to_build: list[str] = []

        for brand, patches_source in patches_by_brand.items():
            if not patches_source:
                continue

            try:
                changelog_text, upstream_date = _fetch_latest_patch_release(
                    patches_source,
                    net,
                    version="dev" if brand in dev_brands else "latest",
                )
            except ResourceNotFoundError:
                epr(f"No upstream release found for '{patches_source}', skipping brand '{brand}'")
                continue
            except Exception as exc:
                # If upstream state cannot be verified, do not manufacture a new public
                # release. The next daily run will retry the check.
                epr(f"Failed to verify upstream release for '{patches_source}': {exc}")
                continue

            our_date = published_builds.get(brand, "")
            if not our_date:
                brands_to_build.append(brand)
                continue
            if not upstream_date or _parse_date(upstream_date) <= _parse_date(our_date):
                continue

            changelog_lower = changelog_text.lower()
            for app in entries_by_brand.get(brand, []):
                if not app.changelog_keywords or any(
                    keyword in changelog_lower for keyword in app.changelog_keywords
                ):
                    brands_to_build.append(brand)
                    break

    print(json.dumps(brands_to_build))


if __name__ == "__main__":
    main()
