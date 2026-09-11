# ADR-0074: Define explicit Filter Cels Target

## Status

Accepted; amended by ADR-0076 for Palette-Entry-only Filter Applications

## Context

Aseprite's native Filter machinery calls its timeline scope `CelsTarget` and offers
`Selected` and `All`. `Selected` reads the current Site range; when that range is
enabled, Aseprite converts the selected Layer set and Frame set into their Cartesian
product, ignores intersections without a Cel, and visits linked Cel data once. Without
an enabled range it falls back to the active Cel. `All` walks the Sprite's unique Cels.

Both modes silently exclude Layers for which `Layer::canEditPixels()` is false. That
test includes the Layer hierarchy's visibility and editability and excludes Reference
Layers. The Filter manager then deduplicates by Image object before applying the
Filter, so Linked Cels that share an Image change together even when only one was in
the selected timeline range.

The public Lua API can set `app.range.layers` and `app.range.frames`, but current range,
active Cel, and saved Filter preferences are ambient editor state. SPA cannot make an
agent-visible request depend on that state. Aseprite's timeline Selected Cels are also
distinct from its pixel Selection mask, which constrains pixels within each target
Image.

## Decision

- Define `Filter Cels Target` as a shared value for Filter Operations only. It is not
  a universal Selector and does not change the target contracts of Image, Paint, Cel,
  Palette, Tilemap, or other Operations.
- Preserve Aseprite's two public variants:
  - `selected` contains a non-empty set of exactly resolved Layer addresses and a
    non-empty set of unique, valid, one-based `frame_numbers`.
  - `all` contains no Layer or Frame members and means every existing Cel on a Layer
    that is natively eligible for pixel editing in the Sprite.
- `selected` denotes the Cartesian product of its resolved Layers and Frame Numbers.
  Existing Cels in that product are the resolved target Cels. Intersections without a
  Cel are native empty intersections: they are reported but are neither created nor
  treated as skipped mutation targets. At least one existing target Cel is required.
- Every explicitly selected Layer must accept Cels and satisfy the native
  `canEditPixels()` precondition. A Group, Reference, hidden, locked, or otherwise
  non-editable requested Layer fails the whole Operation before mutation rather than
  being silently skipped.
- `all` follows Aseprite's native eligibility rule. Its result reports the effective
  eligible Layer/Cel set and the Layers excluded by that rule, so `all` never hides
  what editor state affected the scope. At least one existing target Cel is required.
- Every Filter Application that can mutate Cel Images requires one explicit Filter
  Cels Target. A proven Palette-Entry-only application omits it because no Cel Image
  is an intended mutation target. A required Filter Cels Target never defaults to the
  active Cel, current timeline range, previously saved Filter target, or `all`.
- Before mutation the Lua Kernel installs the explicit `selected` range or selects
  native `all`, resolves the complete target set, and records every empty or excluded
  fact. It restores range and other temporary editor state on success and failure.
- Native linked-image semantics remain authoritative. Each unique target Image is
  filtered once; the Operation Result distinguishes requested timeline intersections,
  resolved target Cels, unique mutated Images, and every affected Linked Cel including
  links outside a `selected` range.
- Pixel Selection Application is an independent explicit request value. Filter Cels
  Target answers which Cels/Images participate; Selection Application answers which
  pixels inside them participate. Neither inherits ambient Sprite or editor state.
- All-or-Nothing Mutation, Background, Tilemap, Color Mode, channel, transaction,
  persistence, and structured-result rules remain operation-specific and apply in
  addition to this target contract.

## Consequences

- Agents can reproduce Aseprite's Filter scope without first manipulating or guessing
  editor state.
- A single explicit contract covers one Cel, a rectangular or discontiguous timeline
  selection, and all natively filterable Cels without adding a generic selector model.
- Empty timeline cells and linked-image fan-out stay visible in results instead of
  being mistaken for silent partial success.
- Eligibility still matches Aseprite rather than introducing a second definition of
  editable pixels.

## Rejected alternatives

### Inherit the current Aseprite range or active Cel

That would make an identical request depend on process-local editor state and would
reintroduce the active-Cel fallback that SPA's explicit targeting rules reject.

### Add one generic Selector shared by every command group

Filter timeline scope is an Aseprite-specific Cartesian Layer/Frame concept. Other
Operations have different cardinality, identity, and ambiguity rules.

### Fail every empty Layer/Frame intersection

An Aseprite timeline Cel range can legitimately include positions without Cels. Those
positions are absence facts, not target objects and not a request for implicit Cel
creation.

### Silently skip an explicitly selected non-editable Layer

Aseprite does this for interactive convenience, but an agent request would receive an
apparently successful partial mutation. SPA instead exposes the precondition failure.
