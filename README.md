# builder-for-morphe

Fork of [nvbangg/builder-for-morphe](https://github.com/nvbangg/builder-for-morphe) for automatically building APKs from [Morphe](https://morphe.software) patch sources.

**Website:** https://zudin987.github.io/#other-tools

> **Fork behavior:** successful APK builds are published automatically so update clients such as Obtainium can detect them. Set the repository variable `ALLOW_PUBLIC_APK_RELEASES=false` if you intentionally want generated releases to remain drafts. This repository is public, so published APK releases are publicly accessible. Only publish third-party app binaries when you have the necessary redistribution rights.

## Build your APKs

1. Fork the upstream repository.
2. Optionally enable/configure the apps you want in [`config.toml`](config.toml).
3. Run the [CI workflow](../../actions/workflows/ci.yml).
4. Successful builds are published as GitHub Releases unless `ALLOW_PUBLIC_APK_RELEASES=false`.

The repository also keeps automatic upstream sync and the local configuration/automation layer used by this fork.

## Documentation

See [CONTRIBUTING.md](CONTRIBUTING.md) for configuration, setup, contribution, and upstream-sync details.

For Morphe resources, patches, and community projects, see [nvbangg/awesome-morphe](https://github.com/nvbangg/awesome-morphe).

## Upstream and license

Original/upstream project: [nvbangg/builder-for-morphe](https://github.com/nvbangg/builder-for-morphe), itself maintained from [krvstek/uni-apks](https://github.com/krvstek/uni-apks).

This project is distributed under the [GNU GPLv3](LICENSE). Original and new copyright notices must remain intact.

- Copyright (C) 2026 [nvbangg](https://github.com/nvbangg) for nvbangg's modifications/contributions.
- Copyright (C) 2026 [krvstek](https://github.com/krvstek) for the original uni-apks codebase.
- See the upstream [Contributors](https://github.com/nvbangg/builder-for-morphe/graphs/contributors) and [`icons/README.md`](icons/README.md) for code/asset attribution.

## Disclaimer

- This project is not affiliated with Morphe or the referenced authors/projects.
- It is intended for educational, research, and personal build workflows.
- Builds use publicly available tools and run through GitHub Actions.
- The workflow can produce patched third-party APKs. Do not publicly redistribute binaries unless you have the necessary rights.
