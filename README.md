# Builder for Morphe

A GitHub Actions builder for creating patched Android APKs from supported Morphe/patch-source projects.

Fork lineage: **nvbangg/builder-for-morphe**, based on **krvstek/uni-apks**.

> **TL;DR:** Choose apps in `config.toml`, run the build workflow, and review the generated **draft** GitHub Release. This fork does **not** publish patched third-party APKs publicly unless the repository variable `ALLOW_PUBLIC_APK_RELEASES` is explicitly set to `true`.

## What this repository does

- Builds selected Android apps with supported patch sources.
- Provides many preconfigured entries in `config.toml`.
- Can react to compatible app/patch updates.
- Stores generated APKs in a GitHub draft Release during normal use.
- Keeps signing credentials in GitHub Secrets rather than source files.
- Supports intentional public Releases only when you explicitly opt in.

## Quick Start — 1, 2, 3

1. Open [`config.toml`](config.toml) and set `enabled = true` only for the apps you want to build.
2. Run the repository's build/CI workflow from **Actions**.
3. Review the generated **draft Release** and download the APKs for your own use/testing.

No public APK publication is required for normal use.

## Public release safety

Public distribution is deliberately **opt-in** in this fork.

- Missing `ALLOW_PUBLIC_APK_RELEASES` → release remains draft.
- `ALLOW_PUBLIC_APK_RELEASES=false` → release remains draft.
- Only `ALLOW_PUBLIC_APK_RELEASES=true` → the release workflow may publish the generated APK release.

If you intentionally want public Releases and have the necessary redistribution rights for every included application, create the repository variable:

```text
ALLOW_PUBLIC_APK_RELEASES=true
```

Do not enable that variable merely to make downloading easier. Patched APKs can contain copyrighted third-party application code and assets; public redistribution may require permission from the relevant rights holders.

## Configuration

Most users only need [`config.toml`](config.toml).

Each app section controls things such as:

- whether the app is enabled,
- stock APK source pages,
- patch source,
- architecture/version options,
- optional branding/patch arguments.

Keep disabled entries disabled unless you actually need them. Smaller build matrices are easier to maintain and produce fewer unnecessary third-party binaries.

For the full configuration and contributing reference, see [CONTRIBUTING.md](CONTRIBUTING.md).

## Secrets and signing

Never commit:

- Android keystores,
- signing passwords,
- `.env` files,
- GitHub/Telegram tokens,
- generated APK/AAB files.

Use GitHub repository **Secrets** for signing credentials. Generated APKs belong in draft Releases/build output rather than the source tree.

## Copyright / redistribution note

This repository contains build automation and configuration. The stock Android apps downloaded during a workflow and the patched APKs produced from them remain subject to their respective owners' copyright, trademark, licence, and distribution terms.

A successful build does **not** automatically grant the right to redistribute the resulting APK publicly.

## Upstream / project credits

- Upstream project: **nvbangg/builder-for-morphe**
- Original base: **krvstek/uni-apks**
- Morphe resources/patch sources remain separate third-party projects.
- Asset-source notes are documented under `icons/` where provided.

This fork is not affiliated with Morphe or the third-party application publishers represented in `config.toml`.

## License

The builder source is distributed under **GNU GPLv3** — see [LICENSE](LICENSE).

Keep the original copyright and attribution notices when redistributing the builder source or modifications.
