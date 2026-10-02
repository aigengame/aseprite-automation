# Issue #36: native Hue/Saturation evidence

## Scope and environment

Validated on macOS with Aseprite 1.3.18.5, using the installed SPA CLI and packaged
Lua handlers. The independent oracle calls `app.command.HueSaturation` directly;
it does not import SPA's parameter map or implement a color formula. Linux results
are reported separately in the PR when available.

Issue #36 owns the feature contract; ADR-0074 owns shared Filter semantics. The
owner approved ordinary Image Layer pixels plus Palette-only applications for
this delivery, with whole-operation refusal of resolved Tilemap pixel targets.
The owner also approved a non-Background Palette Alpha execution anchor, or a
typed refusal if none exists. Both are current delivery boundaries that can be
extended under later requirements and native evidence.

## Discriminating native observations

With RGB `(100, 60, 20, 128)`, Hue `0`, Saturation `30`, Lightness/Value `20`, and
RGB Channels selected, Aseprite returns:

| Public mode | Native mode | Result RGBA |
| --- | --- | --- |
| `hsl-multiply` | `hsl` | `(134, 72, 10, 128)` |
| `hsv-multiply` | `hsv` | `(120, 60, 0, 128)` |
| `hsl-add` | `hsl_add` | `(218, 111, 4, 128)` |
| `hsv-add` | `hsv_add` | `(151, 76, 0, 128)` |

The runtime probe discriminates all four modes through the packaged Filter module
across the delivered applications before advertising the complete Operation.
CLI E2E compares each mode in RGB pixels, Indexed pixels, Indexed Palette Entries,
and RGB Palette plus exact-color matching against the independent command.
Grayscale is separately tested through its applicable Lightness/Alpha path.
Each allowed color component and Alpha has real command-parity coverage.

## Native writeback and ignored-channel boundaries

- Alpha is multiplicative. An Alpha-only adjustment of `50` changes `128` to `192`;
  zero Alpha remains zero at the adjustment stage. Indexed output is still resolved
  through its declared RGB Map, not a second SPA color algorithm.
- A changed Cel can be trimmed at transparent borders. A three-pixel row whose
  first pixel is transparent becomes a two-pixel Image at Canvas x=1. Results
  report both bounds; persisted observation confirms the shift.
- `alpha=-100` deletes a fully transparent target Cel and its same-Layer links,
  including a link outside the requested Frame range. E2E confirms two Cels become
  absent while one unique Image was processed. Results represent absent Cels and
  Images explicitly instead of accessing stale Cel userdata or recreating them.
- Background pixel targets remove Alpha natively. SPA rejects these requests,
  including zero Alpha, before mutation.
- A Background used only as a Palette execution anchor also suppresses Alpha.
  A direct probe returned success while Palette Alpha stayed at `128` for a `50`
  adjustment. SPA now chooses a suitable same-Frame non-Background anchor for
  Palette-mutating Alpha; otherwise it refuses. Regression tests cover refusal,
  alternate anchors, and Indexed Palette-only execution on a Tilemap anchor.
- Indexed Palette-only Alpha changes Palette Entries while ordinary, Tilemap
  placement, and Tile Images remain unchanged. Empty pixel Selection protects
  pixels while RGB Palette adjustment remains explicit.
- An all-zero request bypasses native writeback, retaining bounds and Indexed
  duplicate entries. It still validates targets and supported Channels.

The source explanation is `src/app/commands/filters/filter_manager_impl.cpp`
(`setTarget`/`init` strip Background Alpha), `src/filters/hue_saturation_filter.cpp`
(native arithmetic/Palette paths), and native `PatchCel`/`TrimCel` writeback in the
Aseprite checkout at `375989a61c3425cd4e8cdedfcfcca4bdfef7e1d9`.
These source observations explain the real-runtime results; they do not establish
support for additional runtime versions.

## Reproducible checks

Set `SPA_TEST_ASEPRITE` to the local executable. In the managed macOS sandbox,
follow the existing `SPA_TEST_MACOS_AGENT_SANDBOX=1` setup in `docs/testing.md`.

```sh
uv run --frozen --group test pytest tests/filter
uv run --frozen --group test pytest tests/cli/test_e2e_manifest.py tests/runtime/test_e2e_aseprite.py
uv run --frozen --group test pytest -m 'not e2e'
```

`test_unit_hue_saturation.py` checks the public model and JSON Schema against the
issue's conditional parameters. Integration tests reject missing, contradictory,
or request-mismatched evidence before Target Commit. Shared native state tests
exercise both Filters, including injected post-filter observation failures that
must roll back changes and restore prior Sprite, Layer, Frame, range, Palette Picks,
and Selection. The E2E fixture source and direct oracle live under
`tests/filter/fixtures/hue_*.lua`.
