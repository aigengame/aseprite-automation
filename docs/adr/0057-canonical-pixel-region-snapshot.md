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

Stored pixels and rendered appearance answer different questions. A stored Indexed
Image must retain its Palette Indexes. A composite is a derived observation whose
native rendering semantics depend on the output Color Mode. Treating these as two
encodings of the same result would lose that distinction.

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
- Individual Image reads preserve stored Color Mode and pixel values. Composite
  reads explicitly select a native output Color Mode policy and report the Source
  Color Mode and transparency separately from the output. A caller-selected RGB
  output is a derived RGBA observation, not an alternative authority for stored
  Indexed pixels. It does not convert or save the Source Sprite.
- Render directly into the selected native output format. Do not first compose an
  unsupported Indexed result and then convert its corrupted pixels to RGBA. Native
  Indexed composition and RGB visual blending need not produce equivalent colors
  or opacity. Exact supported choices and refusals belong to the feature issue.
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
- A composite RGB Snapshot cannot replace an Indexed Image under the same-mode
  replacement contract. Explicit conversion is a separate intent.
- Complete state and sparse change have distinct omission semantics.

## Native evidence behind the observation boundary

Aseprite v1.3.18.5's [Group renderer](https://github.com/aseprite/aseprite/blob/375989a61c3425cd4e8cdedfcfcca4bdfef7e1d9/src/render/render.cpp#L1139)
clears an intermediate buffer to zero, including the implicit root Group. In Indexed
output, zero can be an opaque Palette Index instead of the transparent index. Clearing
the outer destination cannot repair this internal buffer. The native
[Indexed-to-Indexed blender](https://github.com/aseprite/aseprite/blob/375989a61c3425cd4e8cdedfcfcca4bdfef7e1d9/src/doc/blend_internals.h#L200)
also preserves indexes without ordinary RGB opacity or Blend Mode mathematics.

Native probes confirmed that direct RGB output interprets the Source mask correctly
and applies Group opacity and blending, without changing Source pixels. This supports
an explicit visual observation intent. It does not by itself prove faithful native
Indexed composition for the affected inputs. Issue #116 adds a bounded native
preserve-Indexed route for nonzero masks: a private loaded document is temporarily
permuted so zero is the native transparent index, then the output indexes and native
state are restored. Its requested Frame Effective Palette must contain the mask and
all returned indexes. This does not introduce a SPA pixel compositor or general
compatibility registry.

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

### Silently fall back from Indexed to RGBA

The caller would receive different rendering semantics and lose Palette Index
identity without choosing that trade-off. Reject unsupported preserve requests;
allow explicit RGB observation independently.
