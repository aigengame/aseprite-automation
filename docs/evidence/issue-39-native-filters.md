# Issue #39: native Despeckle and Convolution evidence

## Scope and environment

Issue #39 owns delivery scope; ADR-0074 owns shared Filter semantics. This slice
adds ordinary Image Layer Despeckle and bounded Convolution discovery. It has no
Convolution callable Descriptor. Local evidence uses macOS Aseprite
`1.3.18.5-dev`, API 41, Lua 5.4. Source inspection uses Aseprite commit
`375989a61c3425cd4e8cdedfcfcca4bdfef7e1d9`. Linux execution is a separate PR CI
result, not inferred from these macOS checks.

## Convolution discovery and native observations

The adapter scans `convmatr.usr`, `convmatr.gen`, then `convmatr.def`, visiting each
native resource directory in order. It uses the prepared launch executable and
environment. This matters on macOS: SPA launches through an isolated executable
link with an adjacent data link. Reported source paths resolve to the installed
files. Linux uses XDG/HOME configuration and executable data/share paths; Windows
uses AppData and executable data. The scanner follows each platform's native
ResourceFinder path rules rather than treating `ASEPRITE_USER_FOLDER` as a
cross-platform resource override.

The scan reports declarations, sources, duplicate names, declared default
Channels, completeness, and notes. Coefficients, divisor, and bias are opaque.
Strict bounds and unsupported syntax stop that file's scan with an incomplete
note; previous complete declarations remain available. A complete metadata scan
does not establish that Aseprite accepts every declaration. No resource registry,
coefficient API, formula evaluator, or replacement convolution engine is added.
The installed macOS default file yielded 39 declarations with no duplicate names.

Native `ConvolutionMatrix` probes begin with RGBA `(10,20,30,40)`:

| Resource | Requested Channel | Observed RGBA after save/reopen |
| --- | --- | --- |
| `brightness` | Red | `(18,28,38,48)` |
| `brightness` | Alpha | `(18,28,38,48)` |
| unknown probe name | Red | `(10,20,30,40)` with command success |

`RuntimeFacts.convolution.probes` retains these requested/observed comparisons.
The Surface Manifest reports an installed Capability Gap and no callable
Descriptor. The native command declares Channels without applying them to its
Filter manager. Resource defaults are discovery facts, not substitute requested
Channels. A later runtime still needs #39's full gate and callable implementation;
this small probe cannot publish a fixed-Resource or fixed-all-components subset.

Relevant native sources: `convolution_matrix_stock.cpp`, `cmd_convolution_matrix.cpp`,
`resource_finder.cpp`, and `filetoks.cpp` under `src/app/`.

## Despeckle observations

- The editor accepts integer width and height in `1..100`. Requests enforce that
  range before invocation. Both odd and even windows are valid, with anchor
  `floor(width/2), floor(height/2)` and upper median at `floor(width*height/2)`.
- Independent native command comparisons cover every RGB Channel subset, all
  Gray/Alpha subsets, Indexed stored-Index median and all eight Indexed RGBA
  component subsets that include Green. Indexed fixtures contain all relevant
  component combinations, allowing exact assertions before any RGB Map ambiguity.
- Indexed component sets without Green are refused in this delivery. The source
  uses the packed RGBA value as a Palette index in the preserved-Green branch.
  On a discriminating seven-entry Palette, Red-only yields Entry 5 instead of
  correct Entry 4; Green-only yields Entry 6 and stored-Index yields Entry 2.
  SPA does not add Green, repair native output, or switch interpretations.
- 1×1 always invokes native Despeckle. With Entries 1 and 2 both
  `(80,120,160,255)`, Index Channels preserve input 1; RGBA component Channels map
  input 1 to 2. Starting at 2 remains unchanged. Save/reopen retains the native
  Index result; Palette Entries do not change.
- Any resolved Tilemap pixel target refuses the whole request before mutation.
  Ordinary targets in mixed documents preserve unrelated Tilemaps. Background
  Alpha refuses instead of silently dropping the flag.
- Explicit Selection limits writeback. Linked Cels outside the requested range
  are reported from the shared Image. Shared state tests inject failure after a
  native effect, then require transaction rollback and restoration of the prior
  active Sprite, Layer, Frame, range, Palette Picks, and both Selections.
- Live Images, Cel geometry and Palette observations must match save/close/reopen
  before Target Commit. Invalid or request-mismatched evidence discards the stage
  and preserves the Source and any previous Target.

Relevant native sources: `src/app/commands/filters/cmd_despeckle.cpp`,
`src/filters/median_filter.cpp`, and `src/filters/neighboring_pixels.h`.

## Native non-wrapped edge sampling

Owner-approved on 2026-10-02: retain native sampling and report the version-specific
defect, rather than promise ideal clamping or implement a replacement algorithm.
`none` disables wrapping; it is not a universal promise of ideal edge repetition.
The same X-axis defect can occur in `y`, where only Y wraps.

On this baseline a 3×3 Grayscale Image has rows `[100,200,40]`, `[200,40,100]`,
and `[40,100,200]`. With width 100, height 1, and `none` or `y`, native Despeckle
returns rows `[100,100,100]`, `[200,200,200]`, and `[40,40,40]`. The second row's
last value differs from the ideal edge-repeat upper median of 100. SPA, direct
native invocation, and saved/reopened output agree.

In `neighboring_pixels.h`, the non-wrapped X loop increments `getx` while `addx`
keeps the pixel address at the left edge. `getx` can reach the image's end before
the address catches up. This explains the observed difference; the Y loop does
not advance `gety` in the same way. The test retains the concrete result and its
difference from ideal clamping. Other covered small windows and X-wrapped cases
also compare against an independent upper-median oracle.

## Reproducible checks

### Windowed editor comparison

On 2026-10-02, six comparisons used the installed macOS windowed editor
(`app.isUIAvailable == true`, version `1.3.18.5-dev`). Each opened a generated
Source, ran the visible Median Blur dialog, confirmed its dimensions and Channels,
accepted the dialog, saved, closed, and reopened the result. All used `none`.

| Color mode | Channels | Window | Reopened editor vs. SPA |
| --- | --- | --- | --- |
| RGB | Red | 3×1 | Equal |
| Grayscale | Gray + Alpha | 2×1 | Equal |
| Indexed | Index | 3×1 | Equal |
| Indexed | Green | 3×1 | Equal |
| Indexed, duplicate Palette colors | Index | 1×1 | Equal; stored Index 1 retained |
| Indexed, duplicate Palette colors | RGBA | 1×1 | Equal; stored Index 1 became 2 |

Equality compares all reopened Cel pixels, Cel geometry, and Palette entries
through `tests/filter/support.py:observe_images`, rather than file bytes. The
fixtures are generated by `tests/filter/fixtures/despeckle_source.lua`; the
windowed runner is `tests/filter/fixtures/despeckle_windowed.lua`. Call the latter
with Source, Target and receipt paths, width, height, `tiled_mode`, and the native
Channel bitmask. Generate the SPA result from the same Source with the matching
explicit request, then compare both outputs with `observe_images`. The runner
requires a visible editor and an explicit dialog confirmation. These six checks
are local evidence, separate from the automated headless suite.

### Automated checks

```sh
uv run --frozen --group test pytest tests/filter tests/runtime/test_e2e_convolution.py
uv run --frozen --group test pytest tests/runtime/test_unit_convolution.py
uv run --frozen --group test pytest -m 'not e2e'
```

Set `SPA_TEST_ASEPRITE` and use the documented macOS sandbox invocation setup when
needed. The Despeckle E2E fixtures invoke an independent native command without
SPA Filter imports; they compare reopened output, not just command success.
