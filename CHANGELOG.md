# Changelog

## [0.2.0](https://github.com/aigengame/aseprite-automation/compare/v0.1.0...v0.2.0) (2026-09-23)


### Features

* **export:** publish a verified RGB PNG Image Artifact ([#77](https://github.com/aigengame/aseprite-automation/issues/77)) ([39a4e90](https://github.com/aigengame/aseprite-automation/commit/39a4e9042dda627bce3a778e2bcc1cdda19b95a8))
* **paint:** apply and verify canonical pixel patches ([#76](https://github.com/aigengame/aseprite-automation/issues/76)) ([e53bd19](https://github.com/aigengame/aseprite-automation/commit/e53bd194245375cb1873bda2a2a262a47fc17f6e))
* **plan:** execute bounded single-Sprite operation plans ([#79](https://github.com/aigengame/aseprite-automation/issues/79)) ([672b562](https://github.com/aigengame/aseprite-automation/commit/672b56242154a9a61351f0c655dbca40feae9ada))
* **runtime:** enforce Aseprite Lua compatibility ([#74](https://github.com/aigengame/aseprite-automation/issues/74)) ([2bd6747](https://github.com/aigengame/aseprite-automation/commit/2bd6747f619e07d31a298ac2ac4ebba5c7374a2b)), closes [#62](https://github.com/aigengame/aseprite-automation/issues/62)
* **sprite:** create, reopen, and inspect RGB sprites ([#75](https://github.com/aigengame/aseprite-automation/issues/75)) ([a287134](https://github.com/aigengame/aseprite-automation/commit/a28713400e4ef47d30bbafcfede21a397417b845))


### Bug Fixes

* **mutation:** unify Source and Target publication identity ([#84](https://github.com/aigengame/aseprite-automation/issues/84)) ([e77b37e](https://github.com/aigengame/aseprite-automation/commit/e77b37e47a0d9a7672a69c06e5954b6c84030657))
* **paint:** reject source aliases to target entries ([#82](https://github.com/aigengame/aseprite-automation/issues/82)) ([38a9414](https://github.com/aigengame/aseprite-automation/commit/38a94142f4acb186f6ae3349a0f2917c95e6ce44))

## 0.1.0 (2026-09-21)


### ⚠ BREAKING CHANGES

* **cli:** process_start_failed details now use the process_start kind instead of process.
* **failure:** Public Kernel Protocol failures use the kernel_protocol category and current-only Kernel Protocol naming.
* **runtime:** The SPA-owned executable setting is SPA_ASEPRITE_EXECUTABLE instead of ASEPRITE_EXECUTABLE.

### Features

* **cli:** ship installed Aseprite info tracer ([#60](https://github.com/aigengame/aseprite-automation/issues/60)) ([06a43d3](https://github.com/aigengame/aseprite-automation/commit/06a43d35098527ee475fa09a1a135ace1a3fce82))
* **failure:** register and project public Failure Codes ([#66](https://github.com/aigengame/aseprite-automation/issues/66)) ([372ca43](https://github.com/aigengame/aseprite-automation/commit/372ca434fde7bc2cb06fbefffce6c2706894c5e1))


### Bug Fixes

* **cli:** close promotion review contract gaps ([fbe5694](https://github.com/aigengame/aseprite-automation/commit/fbe56945eb6e24c27fd51b2c0ec6504303da9d96))
* **cli:** close promotion review findings ([0358c06](https://github.com/aigengame/aseprite-automation/commit/0358c0684820101579266c9e1a2fdd08f8abb6eb))
* **descriptor:** reject stale result operation defaults ([c0ec82f](https://github.com/aigengame/aseprite-automation/commit/c0ec82fd0080d650eb2acbe131d6966a9c8ee666))
* **release:** keep Release PR lockfile in sync ([#73](https://github.com/aigengame/aseprite-automation/issues/73)) ([39970c7](https://github.com/aigengame/aseprite-automation/commit/39970c70ce8a64afb517145963aa8f0c251c22c3))
* **runtime:** classify unexpandable executable paths ([4e6fa81](https://github.com/aigengame/aseprite-automation/commit/4e6fa8183c201644904bcd079fe39cc39b7b16b0))
* **runtime:** launch Aseprite in macOS agent sandboxes ([#63](https://github.com/aigengame/aseprite-automation/issues/63)) ([89d6703](https://github.com/aigengame/aseprite-automation/commit/89d670301670b8d1f9e19a7e5e921e662403dd0c))
