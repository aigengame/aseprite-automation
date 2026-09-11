# ADR-0076: Make FilterWithPalette application explicit

## Status

Accepted

## Context

Aseprite's Brightness/Contrast and Hue/Saturation implementations inherit from
`FilterWithPalette`. Their application destination is not determined only by the
command parameters:

- On an Indexed Sprite with no active pixel Selection, the Filter changes all or the
  currently selected Palette Entries and leaves stored pixel indexes unchanged.
- On an Indexed Sprite with an active pixel Selection, it changes selected pixels as
  RGBA components and maps them back through the active Frame's Palette and RGB Map;
  selected Palette colors are ignored.
- On an RGB Sprite with selected Palette colors, it changes those Palette Entries and
  replaces exact old-Palette-color matches in the targeted pixels with the resulting
  colors.
- On an RGB Sprite without selected Palette colors, and on a Grayscale Sprite, it
  follows its ordinary pixel-processing behavior.

The native branch therefore depends on pixel Selection visibility, selected colors in
the Color Bar, and the active Frame. Those are valid Aseprite capabilities but invalid
implicit inputs for an agent-facing Operation. Aseprite's Lua API can explicitly set
the timeline range and `app.range.colors`; the fixed Kernel can also materialize the
pixel Selection and active Frame required by the chosen native path.

ADR-0074 initially required a Filter Cels Target on every Filter Operation. That is
correct for any branch that can mutate Images, but it is not semantically relevant to
an Indexed Palette-Entry-only branch.

## Decision

- Define `Filter Application` as an operation-specific discriminated value for native
  Filters whose behavior can target Palette state. In the initial catalog, only
  Brightness/Contrast and Hue/Saturation use it.
- Those two Operations publish three explicit variants:
  - `pixels` is available for RGB, Grayscale, and Indexed Sprites. It requires Filter
    Cels Target and applicable Filter Channels and accepts explicit pixel Selection
    Application.
  - `indexed-palette-entries` is available only for Indexed Sprites. It targets one
    exact Palette Change and either all of its entries or a non-empty unique set of
    zero-based Palette Indexes. Filter Cels Target and pixel Selection are invalid.
  - `rgb-palette-colors` is available only for RGB Sprites. It targets one exact
    Palette Change, a non-empty unique set of zero-based Palette Indexes, Filter Cels
    Target, and optional explicit pixel Selection Application.
- `pixels` clears Aseprite Palette Picks before invocation. For an Indexed Sprite it
  requires a one-based `palette_frame_number` whose Effective Palette is the explicit
  RGBA conversion and RGB Map basis. The Kernel selects that Frame and materializes
  the requested pixel Selection. When Selection Application is absent, it installs an
  all-canvas mask to force Aseprite's native pixel path without restricting pixels.
- `indexed-palette-entries` requires `palette_frame_number` to identify an existing
  Palette Change, not merely a Frame at which some earlier Palette is effective. Its
  `entries` value is either `all` or an explicit non-empty set of valid Palette
  Indexes. The Kernel clears the pixel Selection, sets the active Frame and Palette
  Picks, invokes the native Filter, and proves that Palette Entries changed while all
  stored pixel indexes remained unchanged.
- The native Filter machinery requires an active image as an execution anchor even
  when only Palette Entries are intended to change. That anchor is a private Kernel
  mechanism, not a public Cel target. Delivery must prove a non-mutating anchor and
  define the typed unsupported-document outcome when no native-safe anchor exists;
  the Kernel cannot simulate the Filter by reimplementing its color math.
- `rgb-palette-colors` requires `palette_frame_number` to identify an existing Palette
  Change and explicit Palette Indexes. The Kernel sets those Palette Picks plus the
  explicit Cel and pixel-selection scopes. The Operation preserves Aseprite's combined
  behavior: selected Palette Entries change, and exact matches to their old colors in
  participating pixels are replaced with the corresponding new colors.
- Grayscale exposes only `pixels`. Other native Filters have a fixed pixel-application
  meaning and do not receive a meaningless generic `application` field.
- Brightness/Contrast and Hue/Saturation accept only component Filter Channels that
  their implementations affect. They do not publish the `index` channel merely
  because the editor's shared channel widget can encode it.
- Filter Application never inherits pixel Selection, Palette Picks, active Frame,
  active Cel, or saved Filter state. The fixed Lua Kernel sets and restores every
  temporary state value on success and failure.
- Operation Results separately report the Filter Application, Palette basis or exact
  Palette Change, entry changes, targeted and affected Cels/Images, pixel changes,
  Effective Frame Range, and persisted postconditions applicable to that variant.
- Amend ADR-0074: Filter Cels Target is required for every Filter Application that can
  mutate Cel Images. It is absent from a proven Palette-Entry-only variant.

## Consequences

- SPA exposes all material native `FilterWithPalette` outcomes without requiring an
  agent to manipulate invisible editor state first.
- Palette-only, pixel-only, and combined Palette/pixel mutations cannot be confused in
  requests or results.
- Indexed pixel processing gains an explicit Palette basis rather than depending on
  the active Frame.
- The common Filter vocabulary remains proportional: Filters with one application
  destination do not acquire unused union branches.

## Rejected alternatives

### Always force pixel processing

That would discard Aseprite's native Palette adjustment capability and narrow the
business capability without evidence.

### Always preserve Aseprite's ambient branch selection

Identical requests could change a Palette or pixels depending on an earlier editor
action, which is unacceptable for structured agent automation.

### Treat Palette Picks as part of Filter Channels

Channels choose components such as Red or Alpha. Palette Picks choose which Palette
Entries participate; they are different Aseprite concepts with different units.

### Require a Cel target for Indexed Palette-only adjustment

The native implementation may need an internal active-image anchor, but no Cel Image
is part of the intended mutation. Exposing that mechanism would misstate the result.

### Reimplement the adjustment in Lua or Python

That would create a second authority for Aseprite's Filter math and violate the Lua
Kernel DRY boundary.
