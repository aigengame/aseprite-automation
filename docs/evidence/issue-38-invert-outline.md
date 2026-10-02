# Invert Color and Outline native evidence

Scope and acceptance belong to [issue #38](https://github.com/aigengame/aseprite-automation/issues/38).
The implemented Descriptors supply request, result, failure, and installed capability
schemas. This record explains native evidence and how to reproduce it.

## Baseline

- Aseprite 1.3.18.5-dev, API 41, macOS 27.0 arm64.
- Source baseline: `aseprite/aseprite` commit
  `375989a61c3425cd4e8cdedfcfcca4bdfef7e1d9`.
- Real `--batch --script` calls use SPA's prepared invocation environment.
  These results do not constitute windowed UI validation.

## Native observations

| Concern | Evidence and handling |
| --- | --- |
| Invert arithmetic | `src/filters/invert_color_filter.cpp` inverts selected bytes. The Index branch uses `255 - index`; component processing reads the Palette and uses its RGB Map. Independent CLI/native comparisons exercise each applicable Channel. |
| Input bounds | `src/app/commands/filters/filter_manager_impl.cpp` uses `crop_cel_image(cel, 0)`: the source is the full Canvas with zero padding. Native iteration skips by Selection, not transparent Index. A compact Indexed Cel with Palette size 255 rejects full-Canvas inversion (`0 -> 255`) but accepts a Selection over its valid `127 -> 128` pixel. |
| Linked targets | Native selected Frames are ascending and each linked Image is processed once. Reversed requested Frame order preserves the native representative used for index diagnostics. Linked Cel position belongs to shared CelData; moving a link also moves its peers. |
| Outline Matrix | `src/filters/neighboring_pixels.h` traverses top-left first; `outline_filter.cpp` starts with bit 1. The editor displays reversed bit order. Public neighbor names follow sampled Image positions, verified with an asymmetric spatial witness. |
| Outline edges | Native sampling clamps non-tiled axes and wraps tiled axes. A corner fixture produces four distinct results for `none`, `x`, `y`, and `both`. Selection limits candidate writes while neighbors outside Selection remain visible. |
| Outline colors | RGB/Gray candidates classify by zero Alpha or exact background color. Indexed candidates use exact background Index; native neighbor lookup also observes Palette Alpha. The command projects colors through its active Layer once. Mixed RGB/Gray targets use a selected non-Background anchor; Background-only calls retain native opaque projection. Tests compare both target orders and the Background-only case with a direct native oracle. |
| Indexed component Outline | Remains unavailable under the owner-approved baseline gap. SPA refuses it before mutation rather than interpreting it as Index processing. |
| Native writeback | Actual persisted Images and Cel bounds/absence are compared with independently invoked native commands. Pixel-only execution preserves Palette facts; unrelated Tilemaps are checked separately. |
| Empty Selection | The native empty Mask means unrestricted pixels. SPA supplies two selected pixels outside the Canvas, at `(width, 0)` and `(0, height)`, so its bounds start at the Canvas origin and no Canvas pixel is selected. A prior negative-X sentinel made `FilterManagerImpl::applyStep()` lock fewer Mask pixels than the Filter row consumed. Linux exposed an unintended Invert change; macOS reproduced it at widths 8, 16, and 32. The origin-aligned Mask preserves native invocation and Palette application, without changing processed-Image reporting. |
| Result transport | Aseprite's `json_class.cpp` decodes nested objects as userdata and encodes borrowed userdata as null. Results construct ordinary Lua values; Color Values reuse the existing Raster helper. |

## Automated evidence

- `tests/filter/test_unit_invert_outline.py`: request/JSON Schema agreement,
  explicit choices, incompatible Channels/colors, Matrix validation, no Plan Steps.
- `tests/filter/test_e2e_invert_outline.py`: public CLI versus independent native
  command calls, all supported modes and Channels, Matrix presets and asymmetric
  custom neighbors, tiled edges, Selection, Palette limits, two-pass witnesses,
  Background and linked targets, Tilemap refusal and preservation. Empty Selection
  uses both 5-pixel and 8-pixel widths to cover the native Mask byte boundary.
- `tests/filter/test_e2e_pixel_filter_boundaries.py`: explicit Palette time,
  native linked Frame representative, and unchanged Source/Target on refusal.
- `tests/filter/test_e2e_filter_state.py`: success restoration and injected failure
  after a native effect, followed by rollback and restoration.
- Existing Filter tests exercise shared target, Selection, Palette application,
  and publication paths after the shared-mechanism refactoring.

```bash
SPA_TEST_ASEPRITE=/absolute/path/to/aseprite \
  uv run --frozen --group test pytest tests/filter -m e2e
uv run --frozen --group test pytest -m 'not e2e'
```

The two runtime probes exercise RGB, Grayscale, and Indexed supported paths before
the installed Surface Manifest publishes each command. Probe success does not
replace the independent acceptance suite above.
