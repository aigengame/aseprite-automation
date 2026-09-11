# ADR-0028: Preserve Background Layer Cel semantics

## Status

Accepted

## Context

Aseprite permits at most one Background Layer in a Sprite. Unlike a regular
transparent Image Layer, a Background Layer is non-transparent and contains one
full-canvas Cel for every Frame. Its Cels use position `(0, 0)` and full opacity.

Native conversion to Background expands or composites existing Cel Images onto the
canvas, fills transparent areas with a background color, normalizes position and
opacity, and creates filled Cels for Frames that had none. Aseprite's
`Sprite:deleteCel()` also has name-dependent behavior: it removes a Cel from a
transparent Layer but only fills a Background Cel with the background color.

SPA cannot expose one `remove` contract whose result sometimes means absence and
sometimes means replacement pixels. It also cannot depend on an interactive editor's
current background color.

## Decision

- A valid Background Layer is the Sprite's single non-transparent Image Layer and
  has one full-canvas Cel at every Frame.
- Empty Frame Addition creates the required Background Cel using a Background Color
  declared by the `frame add` request rather than Aseprite's editor preference.
- `cel remove` is rejected for a Background Cel because the intersection cannot
  become absent.
- `cel clear` preserves the addressed Cel. On a transparent Layer it clears the
  Image to transparent pixels; on a Background Layer it fills the full canvas with
  the request's explicit Background Color.
- `layer convert-to-background` and `layer convert-from-background` are explicit
  Operations rather than hidden modes of `layer set`.
- `layer convert-to-background` requires an explicit Background Color compatible
  with the Sprite's Color Mode. It reports every created Cel plus Image expansion,
  position normalization, and opacity normalization applied to existing Cels.
- Conversion to Background rejects an existing Background Layer and native-unsupported
  source kinds, including Group, Tilemap, and Reference Layers.
- `layer convert-from-background` preserves existing Cel/Image pixels while changing
  the Layer to a regular transparent Image Layer and reports the resulting facts.
- SPA does not project Aseprite's misleading `deleteCel` name directly into its
  Published Language.

## Consequences

- `remove` always means that a Cel becomes absent.
- Clearing a Background Cel is observable as pixel replacement rather than reported
  as object deletion.
- Conversion captures every destructive or normalizing effect in one typed result.
- Background behavior is deterministic in headless execution because its fill color
  is request data rather than editor state.
- Issues #10 and #13 own Background Layer feature acceptance.

## Rejected alternatives

### Map native `deleteCel` directly to `cel remove`

The same command would mean deletion on one Layer and pixel filling on another.

### Read the current editor background color

That state is hidden from the public request and can differ across installations or
runs.

### Treat the Background Layer as an ordinary transparent Layer

This loses its single-layer, full-canvas, per-Frame, and opacity invariants and would
claim mutations that Aseprite cannot persist faithfully.
