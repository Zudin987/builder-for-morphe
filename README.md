# builder-for-morphe

Personal fork of [nvbangg/builder-for-morphe](https://github.com/nvbangg/builder-for-morphe) for building Morphe-patched APKs with GitHub Actions.

[Published builds](https://github.com/Zudin987/builder-for-morphe/releases) · [Project website](https://zudin987.github.io/projects/morphe-builder/) · [Pull requests](https://github.com/Zudin987/builder-for-morphe/pulls)

This repository is the build configuration and tooling. APK availability depends on the app and successful published builds; check the release notes and architecture before installing.

## Use

1. Configure apps in [`config.toml`](config.toml) if needed.
2. Run the [CI workflow](../../actions/workflows/ci.yml).
3. Review the build output and release notes. Publication follows the repository’s release configuration.

Set repository variable `ALLOW_PUBLIC_APK_RELEASES=false` if you want generated releases to stay drafts.

Only publish third-party APKs when you have the right to redistribute them.

For setup/config details, see [CONTRIBUTING.md](CONTRIBUTING.md).

Upstream: [nvbangg/builder-for-morphe](https://github.com/nvbangg/builder-for-morphe) · [License: GPLv3](LICENSE)
