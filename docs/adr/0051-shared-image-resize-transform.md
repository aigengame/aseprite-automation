# ADR-0051: Use one explicit Image Resize Transform across Raster and Tile authoring

## Status

Accepted

## Context

Aseprite 1.3.18.5 exposes `Image:resize()` with nearest-neighbor as its default and
optional `bilinear` and `rotsprite` methods. Its implementation clamps invalid small
dimensions to 1 and treats an unrecognized method string as nearest-neighbor. For an
Indexed bilinear resize, the native algorithm needs a Palette and RGB Map. A Cel-
attached Image obtains these from its Frame, while a standalone Image uses active
editor state. Non-nearest methods also repair hidden colors in transparent source
pixels before producing the resized Image.

SPA needs the same pixel transform for normal Image authoring and every Tile Bitmap
inside Tileset Resize. It must make method, Palette basis, and source mutation
behavior deterministic without defining a second Tileset-specific algorithm.

## Decision

- Image Resize Transform requires exact positive integer `width` and `height`.
  Zero and negative values fail validation rather than being clamped to 1.
- `method` is required and accepts exactly Aseprite-aligned `nearest-neighbor`,
  `bilinear`, or `rotsprite`. Unknown values fail typed validation instead of falling
  back to nearest-neighbor.
- The output retains the source Image Pixel Format and mask/transparent value
  semantics.
- `nearest-neighbor` samples native stored pixel values directly. `rotsprite` uses
  Aseprite's native stored-value algorithm. For Indexed Images both operate on
  Palette Indexes and need no Palette basis.
- `bilinear` interpolates native RGBA or Grayscale channel values.
- Indexed `bilinear` requires `palette_frame_number`. The Kernel resolves the exact
  Effective Palette and Transparent Color Index, projects indexes to RGBA with the
  transparent index participating at alpha 0, invokes native interpolation, and maps
  results through the same Palette's Aseprite RGB Map without dithering.
- `palette_frame_number` is rejected for non-Indexed Images and for methods other
  than `bilinear`.
- The fixed Lua Kernel applies Aseprite's non-nearest transparent-color fixup and
  resize to a source copy. It replaces the intended Image only after transformation,
  so preprocessing cannot leak source mutation on failure or through shared state.
- Image Resize Transform changes only the Image buffer. Cel position and pivot are
  separate placement semantics.
- Existing linked-Cel rules reduce selected targets to unique shared Images,
  transform each once, preserve sharing, and report every affected Cel.
- `spa image resize` and Tileset Resize `scale` invoke this same Lua Kernel semantic.
- Results include requested and actual dimensions, method, Pixel Format, optional
  Palette Change/effective Frame Range/Transparent Color Index, affected Cels, and
  before/after structural observations and content digest.

## Consequences

- Invalid input cannot silently become a different resize request.
- Indexed interpolation is reproducible without active Palette state.
- Tile Bitmap scaling and ordinary Image scaling cannot drift into separate
  implementations.
- Native transparent-edge preparation is retained without an unintended mutation
  channel.
- Cel placement can evolve independently from the reusable buffer transform.

## Rejected alternatives

### Preserve native defaults and fallbacks

An omitted or misspelled method would silently select nearest-neighbor, hiding caller
intent and schema mistakes.

### Use the active or first Palette for Indexed bilinear

Palette Changes make that basis ambiguous, and active editor state is not part of an
Operation request.

### Implement separate Tile scaling

Tile Images use the same Pixel Formats and resize algorithms. A second semantic
authority would violate DRY and the Lua Kernel boundary.

### Let Image Resize Transform move a Cel

Buffer dimensions and Canvas placement are different domain facts. Pivot behavior
belongs to the Cel-targeted operation that composes the shared transform.

### Run native non-nearest preprocessing on the target source Image

Aseprite repairs hidden transparent colors in place before resize. A source copy
prevents that internal step from escaping the intended replacement transaction.
