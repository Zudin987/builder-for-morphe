# builder-for-morphe

Personal fork of [nvbangg/builder-for-morphe](https://github.com/nvbangg/builder-for-morphe) for building Morphe-patched APKs with GitHub Actions.

[Download latest release](https://github.com/Zudin987/builder-for-morphe/releases) · [Project website](https://zudin987.github.io/projects/morphe-builder/)

This repository is the build configuration and tooling. APK availability depends on the app and successful published builds; check the release notes and architecture before installing.

## Use

1. Configure apps in [`config.toml`](config.toml) if needed. The builder supports APKMirror (`apkmirror-dlurl`) and GitHub Releases (`github-dlurl`) as stock APK sources; Uptodown is not implemented.
2. Run the [CI workflow](../../actions/workflows/ci.yml).
3. Review the build output and release notes. Publication follows the repository’s release configuration.

Set repository variable `ALLOW_PUBLIC_APK_RELEASES=false` if you want generated releases to stay drafts.

Only publish third-party APKs when you have the right to redistribute them.

For setup/config details, see [CONTRIBUTING.md](CONTRIBUTING.md).

## Source status

- `gitlab:Paresh-Maheshwari/paresh-patches` is archived and no longer maintained. Existing Telegram and Truecaller configurations remain available for compatible app versions, but newer app versions may fail to patch. Do not substitute an unrelated bundle without checking patch names, compatible versions, and signatures.
- Upstream `nvbangg/builder-for-morphe` no longer publishes stock APKs. Its old package-specific GitHub release links have been removed; build entries now use their configured APKMirror sources.
- This fork has Issues and Discussions disabled. For reproducible fixes or improvements to this fork, [open a pull request](https://github.com/Zudin987/builder-for-morphe/pulls). Please do not file fork-specific support requests against the original `uni-apks` project.

Upstream: [nvbangg/builder-for-morphe](https://github.com/nvbangg/builder-for-morphe) · [License: GPLv3](LICENSE)
