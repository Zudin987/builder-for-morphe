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

- Speedtest is enabled for ARM64 and ARMv7 using [Android Patches Xtra](https://github.com/BholeyKaBhakt/android-patches-xtra), following that bundle's compatible version rather than the newest stock app. Its patches provide an ad-free account and disable analytics.
- Discord is enabled for ARM64 using [Venus Patches](https://github.com/VenusIsJaded/Venus-Patches). The builder follows Venus's supported Stable APKM and verifies the original Discord signing certificate before patching. After installation, open **Discord Settings > Venus > Features** to enable the features you want; the runtime switches start off. Keep the same signing key for future updates.
- Waze and Adobe Acrobat are disabled. Their configurations are retained for optional future use, and disabled entries are excluded from build-group selection.
- `gitlab:Paresh-Maheshwari/paresh-patches` is archived and no longer maintained. Existing Telegram and Truecaller configurations remain available for compatible app versions, but newer app versions may fail to patch. Do not substitute an unrelated bundle without checking patch names, compatible versions, and signatures.
- Brave uses [kveld9/kveld-morphe-patches](https://github.com/kveld9/kveld-morphe-patches) and follows the version declared compatible by that bundle. It downloads only the architecture-specific Monochrome APK from the matching [official Brave release](https://github.com/brave/brave-browser/releases) and verifies its SHA-256 digest. APKMirror bundles and Universal builds are incompatible and are not fallbacks. Same-day maintenance hotfixes append a newly compatible APK to the existing release while preserving earlier APK assets.
- Upstream `nvbangg/builder-for-morphe` no longer publishes stock APKs. Its old package-specific GitHub release links have been removed; build entries use APKMirror or the official Brave releases as configured.
- This fork has Issues and Discussions disabled. For reproducible fixes or improvements to this fork, [open a pull request](https://github.com/Zudin987/builder-for-morphe/pulls). Please do not file fork-specific support requests against the original `uni-apks` project.

Upstream: [nvbangg/builder-for-morphe](https://github.com/nvbangg/builder-for-morphe) · [License: GPLv3](LICENSE)
