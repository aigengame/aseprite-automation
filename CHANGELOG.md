# Changelog

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
