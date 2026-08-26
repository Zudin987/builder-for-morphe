# builder-for-morphe

Personal fork of [nvbangg/builder-for-morphe](https://github.com/nvbangg/builder-for-morphe) for building Morphe-patched APKs with GitHub Actions.

**Website:** https://zudin987.github.io/#other-tools

## Use

1. Configure apps in [`config.toml`](config.toml) if needed.
2. Run the [CI workflow](../../actions/workflows/ci.yml).
3. Successful builds are published as GitHub Releases by this fork.

Set repository variable `ALLOW_PUBLIC_APK_RELEASES=false` if you want generated releases to stay drafts.

Only publish third-party APKs when you have the right to redistribute them.

For setup/config details, see [CONTRIBUTING.md](CONTRIBUTING.md).

Upstream: [nvbangg/builder-for-morphe](https://github.com/nvbangg/builder-for-morphe) · [License: GPLv3](LICENSE)
