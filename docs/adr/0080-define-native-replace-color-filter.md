# ADR-0080: Define native Replace Color Filter

## Status

Accepted

## Context

Aseprite exposes Replace Color as a native Filter with `from`, `to`, `tolerance`, and
channel inputs. Its editor constrains Tolerance to `0..255`, while the implementation
also clamps arbitrary command input to that range. SPA must reject invalid values
rather than inherit clamping.

For RGB and Grayscale, Aseprite compares each selected component independently. A
pixel matches only when every selected component's absolute difference from `from` is
within the same Tolerance. Unselected components are removed from the match predicate
and retain their source value in the replacement. This is a per-component box test,
not Euclidean color distance.

Indexed execution has two native interpretations. Index mode compares the stored
Palette Index directly and writes `to` as an Index. Component mode resolves `from`,
`to`, and source indexes through the active Palette, compares selected RGBA
components, composes selected replacement components with unselected source
components, and maps the result back through the RGB Map.

The native command wrapper accepts arbitrary Aseprite Colors for an Indexed Layer and
silently maps non-Index colors to an exact or best-fit Palette Entry before filtering.
That hidden conversion has the same effective inputs as supplying the resolved Index,
but it hides a result-affecting quantization decision from the caller.

Equal `from` and `to` values are legal. They are not necessarily a no-op: with a
positive Tolerance, neighboring component values or indexes can be normalized to the
declared replacement. The result must distinguish matched pixels from pixels whose
stored value actually changed.

## Decision

- `spa filter replace-color` is a deterministic pixel Filter Operation that delegates
  to Aseprite's native Replace Color command through one fixed Lua Kernel handler.
- The request requires `from`, `to`, and integer `tolerance` in the inclusive range
  `0..255`. Missing, fractional, non-finite, or out-of-range Tolerance fails before
  invocation; SPA does not inherit native clamping or editor colors.
- RGB requires compatible RGBA Color Values and a non-empty `components` subset of
  `red`, `green`, `blue`, and `alpha`.
- Grayscale requires compatible Grayscale Color Values and a non-empty subset of
  `gray` and `alpha`.
- In component modes, the same Tolerance applies independently to every selected
  component. Every selected component must match. Unselected components neither
  constrain matching nor receive replacement values.
- Indexed requires one-based `palette_frame_number` and exactly one channel
  interpretation:
  - `index` requires `from` and `to` Palette Index Color Values that are valid in the
    resolved Effective Palette. It compares absolute stored-Index distance to
    Tolerance and writes the declared destination Index.
  - `components` requires `from` and `to` Palette Index Color Values plus a non-empty
    subset of `red`, `green`, `blue`, and `alpha`. Their resolved Effective-Palette
    RGBA values supply matching and replacement, and Aseprite's RGB Map quantizes the
    composed result.
- Indexed `from` and `to` never accept RGBA or Grayscale values for implicit exact or
  best-fit conversion. Direct Palette Index input expresses every effective native
  source/destination while keeping the conversion observable.
- Equal `from` and `to` is valid. The Operation reports both `matched_pixel_count` and
  `changed_pixel_count`; it calls the outcome a no-op only when no stored target pixel
  changed, not from field equality alone.
- Replace Color always requires Filter Cels Target and accepts explicit pixel
  Selection Application. It has no Filter Application union and never mutates Palette
  Entries.
- Background Alpha, target eligibility, Linked Image, all-or-nothing mutation, state
  restoration, and persistence rules apply. An Alpha request fails if any target is a
  Background Cel.
- The request accepts no Tiled Mode, per-component Tolerance, Euclidean or perceptual
  distance, HSV/Lab matching, replacement palette-growth policy, dithering, or custom
  quantizer.
- Aseprite owns component comparison, matching conjunction, replacement composition,
  stored-Index comparison, Palette lookup, and RGB Map quantization. Lua and Python do
  not reproduce or substitute these algorithms.
- The Operation Result reports canonical `from`, `to`, and Tolerance; effective
  Channels; Indexed resolved Palette colors and basis; Filter Cels Target and
  Selection facts; matched and changed counts; unique Images and all affected Cels;
  changed bounds; and persisted before/after content observations.
- Delivery requires real-runtime parity across zero and positive Tolerance, partial
  Channels, transparent values, every Color Mode, Indexed Index/component paths,
  Selection, Background and linked targets, equality/normalization cases, rollback,
  restoration, and save/close/reopen verification.

## Consequences

- Agents can select exact native matching semantics without hidden color-distance or
  Indexed best-fit assumptions.
- Palette Index input makes every result-affecting Indexed source and destination
  explicit while retaining all effective native behaviors.
- Separate matched and changed counts explain normalization, identity, and Selection
  outcomes accurately.
- More advanced perceptual matching or palette growth remains a distinct future
  Aseprite capability rather than an option bag on Replace Color.

## Rejected alternatives

### Accept arbitrary Indexed RGBA Colors

Aseprite silently converts them to an exact or best-fit Palette Entry before the
Filter runs. Requiring that effective Index removes hidden quantization without
removing an executable result.

### Define Tolerance as one aggregate color distance

The native implementation compares each selected component independently and requires
all comparisons to pass.

### Treat equal source and destination as an unconditional no-op

Positive Tolerance can replace neighboring values with the declared source/destination
value, changing stored pixels even when the two fields are equal.

### Allow per-channel Tolerance

Aseprite exposes one shared Tolerance. Multiple tolerances would be a new matching
algorithm.

### Implement custom Palette quantization

That would create a second authority and diverge from the declared Effective Palette
and Aseprite RGB Map.
