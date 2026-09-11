# ADR-0057: Use one canonical Pixel Region Snapshot for Raster exchange

## Status

Accepted

## Context

Agents need structured, lossless Image pixel inspection and replacement. A dense
array of tagged Color Values is verbose, while a sparse representation needs a hidden
default. Large results also need Artifact transport without creating a second Raster
encoding.

The value must preserve native Indexed pixels rather than making rendered RGBA a
second authority, and it must distinguish pixel replacement from geometry or Color
Mode changes.

## Decision

- Pixel Region Snapshot is the complete canonical Raster value for one positive
  half-open Rectangle in Image Pixel space.
- It declares Aseprite `color_mode` and contains exactly `height` ordered rows.
- Each row is an ordered sequence of runs. Every run has a positive `length` and one
  Color Value compatible with the declared Color Mode; lengths total `width` exactly.
- Adjacent runs with equal Color Values must be merged. Row order and run lengths
  imply each relative pixel coordinate, yielding one canonical representation.
- No pixel is omitted and there is no transparent or other default value.
- RGB snapshots use `rgba`, Grayscale snapshots use `grayscale`, and Indexed
  snapshots preserve stored `palette-index` values. No implicit Color Mode change or
  RGBA expansion becomes authoritative.
- Inline JSON and JSON Artifact forms use the same schema. A value exceeding the
  inline Domain Bound is emitted as a complete Artifact without truncation or an
  alternate encoding.
- Descriptor schemas validate the transport shape. The fixed Lua Kernel owns
  semantic coverage checks, Color Value compatibility, canonicalization, Image reads,
  and Image writes. Python transports schema-valid JSON or Artifact references and
  does not own a second codec.
- `spa image get` requires one positive Rectangle fully contained in an existing
  non-Tilemap Cel Image. It returns the exact complete Snapshot plus Color Mode,
  mask/transparent value, Layer kind, associated Cels and Image sharing, and the
  target Frame's Effective Palette facts for Indexed content. No clipping occurs.
- `spa image replace` accepts a Snapshot inline or from a JSON Artifact. Its Rectangle
  must equal the current Image's full `(0,0,width,height)` bounds and its Color Mode
  must match the target.
- Replace changes stored pixel content without changing Image dimensions, Cel
  positions, Color Mode, Background invariants, Reference floating-point bounds, or
  native Image sharing. Resize, Crop, Canvas Resize, and Change Color Mode express
  those other intents.
- Get and Replace support existing Cels on ordinary Image, Background, and Reference
  Layers. Tilemap Cels use Tilemap values; absent and non-Cel targets fail.
- Selection state is not read or applied. Replacement is an all-or-nothing Mutation.
- Replace results return input form, complete affected Cel/link facts, unchanged
  geometry, Pixel Format, and before/after content digest. Save/close/reopen verifies
  persisted facts.

## Consequences

- Agents and Artifacts exchange one lossless, inspectable Raster structure.
- Run-length rows reduce common pixel-art repetition without an implicit fill rule.
- Indexed round-trips preserve native Palette Indexes.
- Pixel replacement cannot silently resize, reposition, or convert an Image.

## Rejected alternatives

### Dense tagged Color Value arrays

They are canonical but unnecessarily repeat common pixel-art colors.

### Sparse pixels with an implicit transparent default

Background Images and opaque content do not share that default, and omission would
be ambiguous for complete replacement.

### Use a binary encoding for large Snapshots

It would create a second public Raster representation instead of changing transport.

### Let `image replace` change dimensions or Color Mode

Those intents already have explicit operations and materially different invariants.
