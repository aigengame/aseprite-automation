# ADR-0057: Use canonical Snapshot and Patch values for Raster exchange

## Status

Accepted

## Consolidates

This record consolidates ADR-0058. Image get and replace delivery is owned by issue
#20; exact Pixel Patch application is owned by issue #5.

## Context

Agents need a lossless complete Raster value for inspection and replacement and a
compact sparse value for exact edits. A sparse representation cannot use one omitted-
pixel rule for both meanings. Large payloads also need Artifact transport without
creating a second Raster encoding.

The value must preserve native Indexed pixels rather than making rendered RGBA a
second authority, and it must distinguish pixel replacement from geometry or Color
Mode changes.

## Decision

- Pixel Region Snapshot is the complete canonical Raster value for one positive
  half-open Rectangle in Image Pixel space.
- Serialized Snapshot pixels are rebased to the local Image Pixel Rectangle
  `(0,0,width,height)`. An Operation that reads from Canvas Pixel or another source
  Coordinate Space reports that source space and source Rectangle separately.
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
  inline Operation Limit is emitted as a complete Artifact without truncation or an
  alternate encoding.
- Descriptor JSON schemas validate the transport shape. Python request contracts can
  reject static canonical wire violations, such as Patch runs outside their declared
  Rectangle, out-of-order or overlapping runs, and adjacent equal runs. The fixed Lua
  Kernel repeats these checks before mutation and owns document-dependent coverage,
  native Color Mode compatibility, Image reads, and Image writes. Python does not own
  a second Raster codec or normalize native pixel content.
- Pixel Patch is the canonical sparse Raster mutation value for one declared positive
  Rectangle. Its ordered, non-overlapping runs use absolute Image Pixel coordinates,
  positive lengths, and compatible Color Values. Adjacent equal values are merged.
- Listed Patch pixels receive exact stored values; omitted pixels remain unchanged. An
  empty run list is an explicit no-op.
- Snapshot replacement, Patch application, compositing, geometry transformation, and
  Color Mode conversion remain distinct authoring intents. Their target, clipping,
  Selection, Palette applicability, and result contracts belong to their feature
  issues.

## Consequences

- Agents and Artifacts exchange one complete and one sparse lossless Raster structure.
- Run-length rows reduce common pixel-art repetition without an implicit fill rule.
- Indexed round-trips preserve native Palette Indexes.
- Complete state and sparse change have distinct omission semantics.

## Rejected alternatives

### Dense tagged Color Value arrays

They are canonical but unnecessarily repeat common pixel-art colors.

### Sparse pixels with an implicit transparent default

Background Images and opaque content do not share that default, and omission would
be ambiguous for complete replacement.

### Use one representation for complete and sparse intent

Omission would have to mean both a default pixel and unchanged state.

### Use a binary encoding for large Snapshots

It would create a second public Raster representation instead of changing transport.

### Let transport select a different Raster model

Artifact transport changes payload location, not value semantics.
