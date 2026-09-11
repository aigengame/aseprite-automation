# ADR-0053: Keep Image Crop contained and make Cel movement explicit

## Status

Accepted

## Context

Aseprite can construct a new Image from a Rectangle of another Image, while its
internal Cel crop behavior can also change the Cel origin. These are related but
different facts: one chooses retained Image Pixels, and the other decides whether
those pixels remain at their former Canvas positions.

Allowing a crop Rectangle outside the source would additionally turn the Operation
into canvas enlargement and padding with an implicit fill value. SPA needs both
capabilities, but their requests and postconditions should not overload one name.

## Decision

- `spa image crop` applies to an existing Cel on an ordinary transparent Image Layer.
- The request contains one non-empty half-open Rectangle in source Image Pixel space.
  It must be fully contained by the source Image bounds.
- The new Image has the Rectangle's `width/height`, retains the source Pixel Format
  and mask/transparent semantics, and maps the source Rectangle origin to `(0,0)`.
- The request requires one Image Crop Cel Position Policy:
  - `preserve_canvas_pixels` adds the Rectangle's `x/y` to every affected Cel Canvas
    Pixel position, so retained pixels remain at the same Canvas coordinates.
  - `keep_cel_position` leaves every affected Cel position unchanged, placing the
    retained region at the existing Cel origin.
- A linked Image is cropped once. The same selected position offset applies to every
  Cel sharing it, and native sharing remains intact. Isolated behavior requires
  `cel unlink` first.
- Tilemap, Background, Reference, absent, and non-Cel targets are rejected because
  they have different content or geometry invariants.
- Rectangle validation, Image replacement, and all Cel position changes execute as
  one all-or-nothing Mutation.
- Results return requested and applied source Rectangle, old/new Image bounds, policy
  and position offset, all affected Cels and links, Pixel Format, and before/after
  content digest. Save/close/reopen verification confirms them.
- Out-of-bounds copy, padding, explicit fill, and Image enlargement belong to a
  separate Image Canvas Operation.

## Consequences

- Agents can choose whether crop preserves Canvas appearance or Cel origin.
- Crop has one precise meaning and never hides clipping or padding.
- Linked-Cel behavior remains consistent with other Raster mutations.
- A later Image Canvas Operation can support enlargement without weakening Crop
  postconditions.

## Rejected alternatives

### Always move the Cel with the crop origin

Keeping the Cel origin while shifting retained content is also a valid Image editing
intent and should remain explicit.

### Allow out-of-bounds Crop with implicit fill

That combines content removal with canvas enlargement and requires an undeclared
fill Color Value.

### Interpret the Rectangle in Canvas Pixel space

This Operation selects an Image-buffer region. Sprite Crop and Cel placement use
Canvas Pixel space separately.

### Break Linked Cels automatically

Raster mutations preserve native sharing. An isolated crop begins with explicit
`cel unlink`.
