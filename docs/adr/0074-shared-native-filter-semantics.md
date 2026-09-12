# ADR-0074: Define shared native Filter semantics

## Status

Accepted

## Consolidates

- Former ADR-0075: typed Filter Channels.
- Former ADR-0076: explicit palette-aware Filter Application.

## Context

Aseprite implements a cohesive family of batch pixel Filters. The native Filter
manager combines several kinds of editor state: timeline scope, active Cel and Frame,
pixel Selection, component-channel flags, Palette Picks, saved Filter preferences, and
Linked Cel Images. These inputs are convenient in the interactive editor but cannot be
ambient inputs to a reproducible agent Operation.

The same machinery also has meaningful native variation. Some Filters process stored
Palette Indexes, some process color components through an Effective Palette, and
`FilterWithPalette` operations can mutate pixels, Palette Entries, or both. A universal
request shape would admit combinations that a particular native Filter ignores.

SPA therefore needs one shared Filter vocabulary without replacing Aseprite's
operation-specific semantics or creating a generic selector, effect, or image-processing
system. Feature issues own exact fields, acceptance, runtime evidence, and Capability
Gaps. Installed Operation Descriptors and the Surface Manifest own shipped schemas.

## Decision

### Filter Cels Target

- `Filter Cels Target` is a shared value for Filter Operations only. It is not a
  universal Selector and does not redefine Image, Paint, Cel, Palette, Tilemap, or
  other target contracts.
- It preserves Aseprite's `selected` and `all` meanings while making the choice and
  all addresses explicit. It never inherits the active Cel, current range, saved
  Filter target, or an implicit `all`.
- `selected` resolves the Cartesian product of exact Layer and Frame choices to
  existing Cels. Empty intersections remain native absence facts. An explicitly
  requested Layer that cannot edit pixels fails the Operation before mutation instead
  of being silently skipped.
- `all` follows Aseprite's native pixel-editability rule and reports both its effective
  targets and exclusions. Every target form must resolve at least one existing Cel.
- Native Linked Cel sharing remains authoritative. Each unique target Image is filtered
  once, and the Result reports every affected Cel, including links outside an explicit
  selected range.

### Filter Channels

- `Filter Channels` uses named, typed values rather than Aseprite's internal integer
  bitmask. `components` and stored `index` are exclusive interpretations.
- Component names follow Color Mode: RGB uses Red, Green, Blue, and Alpha; Grayscale
  uses Gray and Alpha; Indexed component processing uses RGBA through an explicit
  Effective Palette basis.
- Each Operation Descriptor owns the non-empty Channel subsets that its native Filter
  demonstrably affects. Encoding a native flag is not evidence that the Filter supports
  it. Empty, unknown, incompatible, ignored, and unsupported Channels fail before
  mutation.
- Channels are explicit and never inherit native defaults, editor button state,
  selected Palette Entries, or an earlier Operation. If Alpha is requested and any
  resolved target is a Background Cel, the whole Operation fails instead of silently
  changing the effective Channel set for part of the request.
- The fixed Lua Kernel is the sole authority that maps typed Channels to native Filter
  flags. Public callers cannot provide a raw mask.

### Selection and palette-aware application

- Filter Cels Target chooses participating Cels and Images. Pixel Selection Application
  independently chooses pixels within them. Neither inherits ambient editor state.
- A native Filter that can target Palette state uses an explicit, operation-specific
  `Filter Application` value. The shared meanings distinguish pixel mutation,
  Indexed Palette-Entry-only mutation, and RGB Palette plus matching-pixel mutation.
  Filters with one fixed pixel destination do not receive an `application` field.
- A branch that can mutate Cel Images requires Filter Cels Target. A proven
  Palette-Entry-only branch omits it because no Cel Image is an intended mutation
  target; any active image required by Aseprite is a private Kernel execution anchor.
- Indexed component processing declares the Frame whose Effective Palette and RGB Map
  form the conversion basis. Palette-mutating branches identify an exact Palette
  Change and explicit Palette Entries. No branch inherits active Frame, Palette Picks,
  pixel Selection, or saved Filter state.

### Execution authority and reporting

- Aseprite owns each Filter's raster and color algorithm. The packaged Lua Kernel owns
  typed-to-native mapping, invocation, temporary editor-state installation and
  restoration, native observation, and the structured execution result.
- Python may orchestrate the application use case and validate the public request, but
  it cannot implement a second Filter algorithm, create a generated operation script,
  or define a competing native mapping.
- Existing all-or-nothing mutation, Target Commit, Background, Palette, persistence,
  and structured-result decisions apply. Results expose the effective target,
  Selection, Channels, application and Palette basis where applicable, unique mutated
  Images, all affected Linked Cels, and persisted observations.
- Exact parameters, allowed combinations, result fields, version gates, tests, and
  Capability Gap evidence belong to the owning feature issue until delivery and to the
  installed Operation Descriptor and Surface Manifest after delivery.

## Consequences

- Agents can reproduce native Filter behavior without first manipulating or guessing
  invisible editor state.
- Shared target, Channel, Selection, Palette, Linked Cels, and authority rules remain
  consistent across Filters while each Filter keeps a strict operation-specific schema.
- Palette-only, pixel-only, and combined mutations cannot be confused in requests or
  results.
- Native defects remain visible as versioned Capability Gaps rather than motivating
  silent partial support or a duplicate image-processing implementation.

## Rejected alternatives

### Inherit editor state

Identical requests could mutate different Cels, pixels, components, or Palette Entries
after an unrelated editor action.

### Define a universal Selector, Filter request, or raw Channel mask

Different Operations and Filters have different identity, cardinality, supported
Channels, and application destinations. Flattening them would legitimize invalid or
ignored combinations.

### Force every palette-aware Filter through one pixel path

That would remove native Palette capabilities and conceal the distinction between
Palette and Image mutations.

### Reimplement Filter behavior in Lua or Python

That would create a second authority for Aseprite's raster, color, rounding, Palette,
and RGB Map semantics.
