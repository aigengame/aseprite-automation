# ADR-0051: Share Image-buffer transforms across Raster and Tile authoring

## Status

Accepted

## Consolidates

This record consolidates ADR-0054. Image resize delivery is owned by issue #21, Image
crop and canvas-resize delivery by issue #22, and Tileset resize delivery by issue #45.

## Context

Aseprite 1.3.18.5 exposes `Image:resize()` with nearest-neighbor as its default and
optional `bilinear` and `rotsprite` methods. Its implementation clamps invalid small
dimensions to 1 and treats an unrecognized method string as nearest-neighbor. For an
Indexed bilinear resize, the native algorithm needs a Palette and RGB Map. A Cel-
attached Image obtains these from its Frame, while a standalone Image uses active
editor state. Non-nearest methods also repair hidden colors in transparent source
pixels before producing the resized Image.

In Aseprite 1.3.18.5, native Indexed interpolation reads the Image's mask when it
projects source indexes to RGBA, but `Sprite::rgbMap()` selects its output mask from
the first RGBA-zero Palette entry, or index 0 when none exists. This can differ from
the Sprite's Transparent Color Index. A detached `Image:drawImage()` also reads the
process-global Palette, which need not match the declared Frame in batch mode.

SPA needs the same resize and non-scaling canvas-copy transforms for ordinary Image
authoring and every Tile Bitmap inside Tileset Resize. It must make interpolation,
Palette basis, source mutation, offsets, clipping, and fill deterministic without
defining Tileset-specific algorithms. Cel placement remains an outer concern that Tile
Bitmaps do not have.

## Decision

- Image Resize Transform requires exact positive integer `width` and `height`.
  Zero and negative values fail validation rather than being clamped to 1.
- `method` is required and accepts exactly Aseprite-aligned `nearest-neighbor`,
  `bilinear`, or `rotsprite`. Unknown values fail typed validation instead of falling
  back to nearest-neighbor.
- The output retains the source Image Color Mode and mask/transparent value
  semantics.
- `nearest-neighbor` samples native stored pixel values directly. `rotsprite` uses
  Aseprite's native stored-value algorithm. For Indexed Images both operate on
  Palette Indexes and need no Palette basis.
- `bilinear` interpolates native RGBA or Grayscale channel values.
- Indexed `bilinear` requires `palette_frame_number`. The Kernel resolves the exact
  Effective Palette and Transparent Color Index, projects indexes to RGBA with the
  transparent index participating at alpha 0 while retaining its Palette RGB, and
  invokes native bilinear interpolation for the RGB and alpha channels. It maps each
  result through the original Effective Palette with Aseprite 1.3.18.5's Palette
  best-fit criterion and the Sprite's Transparent Color Index as the excluded mask.
  Alpha below 8 maps to that transparent index. Mapping uses no dithering or
  process-global Palette state. Like native Palette best-fit, mapping considers the
  first 256 entries; the reported Palette size remains the full Effective Palette size.
- `palette_frame_number` is rejected for non-Indexed Images and for methods other
  than `bilinear`.
- The fixed Lua Kernel applies native non-nearest resize to detached source data.
  For Indexed bilinear, it keeps source RGB above zero alpha during interpolation and
  carries the actual alpha separately so native transparent-color fixup cannot erase
  hidden Palette RGB. It replaces the intended Image only after transformation, so
  preprocessing cannot leak source mutation on failure or through shared state.
- Image Resize Transform changes only the Image buffer. Cel position and pivot are
  separate placement semantics.
- Existing linked-Cel rules reduce selected targets to unique shared Images,
  transform each once, preserve sharing, and report every affected Cel.
- Image and Tileset resize Operations invoke this same Lua Kernel semantic.
- Image Canvas Transform is a second pure Image-buffer semantic owned by the same fixed
  Lua Kernel. It requires exact positive target dimensions, an integer offset, and an
  explicit Color Value compatible with the source Color Mode.
- Canvas Transform places source Image Pixel `(0,0)` at the declared offset in a filled,
  same-format target Image. It copies intersecting stored pixels 1:1, discards source
  pixels outside the target, and retains the fill in uncovered pixels.
- A Canvas Transform with no source/target intersection is a valid deterministic
  fill-only result. It does not center, scale, apply Selection, change Color Mode, or
  resize the Sprite canvas.
- Each owning Image or Tileset Operation separately defines applicable targets, linked
  Image behavior, Cel-position policy, and Operation-specific result facts.

## Consequences

- Invalid input cannot silently become a different resize request.
- Indexed interpolation is reproducible without active Palette state.
- Duplicate Palette colors can yield a different stored index from Aseprite's native
  Octree RGB Map; the declared Palette best-fit rule chooses the first equally good
  non-transparent index. The original Palette is not rewritten. The Indexed path
  requires two native channel resizes and per-pixel projection and mapping.
- Tile Bitmap transforms and ordinary Image transforms cannot drift into separate
  implementations.
- Native RGB and Grayscale transparent-edge preparation stays on detached data.
  Indexed interpolation retains hidden Palette RGB and the declared mask.
- Cel placement can evolve independently from reusable buffer transforms.

## Rejected alternatives

### Preserve native defaults and fallbacks

An omitted or misspelled method would silently select nearest-neighbor, hiding caller
intent and schema mistakes.

### Use the active or first Palette for Indexed bilinear

Palette Changes make that basis ambiguous, and active editor state is not part of an
Operation request.

### Normalize the transparent Palette entry before native Indexed resize

Changing it to RGBA zero loses its hidden RGB during interpolation and can change
adjacent output indexes. Other RGBA-zero entries can still take the output mask.

### Implement separate Tile scaling

Tile Images use the same Color Modes and resize algorithms. A second semantic
authority would violate DRY and the Lua Kernel boundary.

### Let Image Resize Transform move a Cel

Buffer dimensions and Canvas placement are different domain facts. Pivot behavior
belongs to the Cel-targeted operation that composes the shared transform.

### Run native non-nearest preprocessing on the target source Image

Aseprite repairs hidden transparent colors in place before resize. A source copy
prevents that internal step from escaping the intended replacement transaction.

### Implement Tile canvas resizing separately

That would violate the Lua Kernel's DRY authority over offset, clipping, fill, and copy
semantics.

### Require a non-empty copied intersection

Exact size, offset, and fill already define a deterministic fill-only Image. An overlap
guard would add policy without adding authoring capability.
