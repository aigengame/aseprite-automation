# ADR-0075: Define typed Filter Channels

## Status

Accepted; complemented by ADR-0076 for Indexed Palette and application semantics

## Context

Aseprite's native Filter implementation represents channels as an integer bitmask
containing Red, Green, Blue, Alpha, Gray, and Index flags. The editor presents named
buttons instead. RGB and Indexed Sprites show R, G, B, A, and, for Indexed Sprites,
Index; Grayscale Sprites show Gray and Alpha. The editor prevents Index from being
selected together with RGBA components.

The bitmask is not a stable agent-facing domain value. It admits unknown bits,
Color-Mode-incompatible combinations, an empty set, and combinations that a specific
Filter silently ignores. The native commands also use different defaults and do not
all implement every visible channel. For example, Brightness/Contrast does not change
Alpha or implement Index processing, while other Filters can operate on Alpha, Index,
or both kinds of Indexed interpretation.

The Filter manager removes Alpha when it processes a Background Cel. In a multi-Cel
request, silently removing a requested channel for one target would violate SPA's
explicit, all-or-nothing Operation contract.

Indexed component processing additionally depends on Palette semantics, and some
native Filters can modify Palette Entries rather than pixel indexes. That application
destination and Palette basis require their own decision; they must not be smuggled
into the channel representation.

## Decision

- Define `Filter Channels` as a shared public vocabulary used only by Filter
  Operations. Each Filter Descriptor owns the subset and combinations that its native
  implementation actually supports.
- Publish two discriminated forms:
  - `components` contains one non-empty set of named component channels.
  - `index` contains no component members and denotes Aseprite's stored Palette Index
    channel.
- Valid component names are Color-Mode-specific:
  - RGB: `red`, `green`, `blue`, and `alpha`.
  - Grayscale: `gray` and `alpha`.
  - Indexed component interpretation: `red`, `green`, `blue`, and `alpha` through an
    explicitly governed Palette basis.
- `index` is valid only for an Indexed Sprite and only for a Filter whose native
  implementation demonstrably processes the Index channel. It cannot be combined
  with component channels.
- A request list contains unique names. The Operation Result returns the effective
  channels in canonical Color-Mode order rather than preserving caller order as
  semantic data.
- Every Filter request supplies Filter Channels explicitly. SPA does not inherit the
  native command's default mask, editor button state, selected Palette Entries, or an
  earlier Operation's channels.
- A Filter Descriptor rejects an empty set, duplicate names, unknown channels,
  Color-Mode-incompatible channels, and channels that its native Filter ignores or
  cannot affect. SPA never accepts a known no-op merely because Aseprite's integer
  bitmask can encode it.
- If any resolved target is a Background Cel, a request containing `alpha` fails
  preflight for the whole Operation. SPA does not silently remove Alpha for only those
  targets. An agent can issue separate Operations with compatible channel sets.
- The fixed Lua Kernel is the authority that maps validated named channels to native
  Filter flags. Python schemas and adapters may validate and transport the public
  value but cannot define a second mapping or pass a caller-supplied raw mask.
- Each Filter issue owns the real-runtime evidence for published and rejected
  Channels; issue #35 establishes the shared contract.
- This decision does not choose whether an Indexed Filter applies to pixel indexes,
  component colors, or Palette Entries, nor which Effective Palette supplies the
  component basis. Those remain a separate explicit Filter application decision.

## Consequences

- Descriptors expose agent-readable channel intent without leaking internal bit
  constants.
- Color Mode and Filter capability errors are discovered before mutation.
- Background and multi-target behavior cannot degrade into unreported partial channel
  application.
- SPA can preserve useful Indexed modes while separately resolving their Palette and
  mutation-scope semantics.

## Rejected alternatives

### Expose Aseprite's integer bitmask

That would expose a private representation, permit invalid bits, and make schemas
unable to explain the requested channel meaning.

### Publish one universal list for every Filter

Native implementations do not honor the same channels. A schema that accepts every
named channel would legitimize silent no-ops.

### Offer an implicit `all` default

Native defaults differ by Filter and can include flags that the implementation does
not use. Explicit named channels make the Operation independent of those defaults.

### Strip Alpha from Background targets

That would silently execute a different request on part of a multi-Cel target set.

### Combine Index and component channels

Aseprite's UI treats these as exclusive interpretations, and native Indexed filter
code branches between them rather than applying both.
