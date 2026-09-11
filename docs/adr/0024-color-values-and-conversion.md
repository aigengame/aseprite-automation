# ADR-0024: Preserve Color Mode semantics in public Color Values

## Status

Accepted

## Context

Aseprite Images store different native pixel values according to the Sprite's Color
Mode. RGB pixels contain RGBA channels, Grayscale pixels contain gray and alpha, and
Indexed pixels contain a Palette Index. `Sprite.transparentColor` is a special index
for transparent Layers of an Indexed Sprite rather than an alpha channel. Aseprite's
packed pixel integer is interpreted according to the active Sprite, so the same public
integer would not have one context-free meaning.

Aseprite can also convert between Color Modes, choose a nearest Palette entry, and
apply quantization, fit, grayscale, or dithering behavior. Some native defaults can
depend on editor preferences. Implicitly applying them during Paint would make an
apparently identical request depend on hidden state.

## Decision

The Published Language defines one discriminated **Color Value** family:

- `rgba` contains integer `red`, `green`, `blue`, and `alpha` components from 0
  through 255.
- `grayscale` contains integer `gray` and `alpha` components from 0 through 255.
- `palette-index` contains an integer `palette_index` that must exist in the Palette
  applicable to the target Frame.

The discriminator is required. SPA does not publish untagged channel tuples or
Aseprite packed pixel integers.

For an Indexed Image, the native pixel value remains its Palette Index. Inspection
can additionally report an RGBA Color Value resolved through the applicable Palette,
but the resolved value is a separate observation and does not replace the index.
The Sprite's Transparent Color Index remains distinct from RGBA or Grayscale alpha.

Image and Paint Operations require Color Values compatible with the target Sprite's
Color Mode unless their contract includes explicit operation-specific conversion
inputs. Sprite-wide conversion uses Aseprite's native **Change Color Mode** operation.
Every applicable request exposes the result-affecting Palette mapping, Grayscale,
quantization, RGB Map Algorithm, Color Best Fit Criteria, and Dithering choices rather
than defining a parallel Color Conversion framework. Ordinary Paint does not silently
choose a nearest color or consult an undeclared editor preference.

Color Mode is independent of Aseprite's **Color Profile**, which describes how stored
color values are interpreted. ADR-0093 defines Assign Color Profile, Convert Color
Profile, and export behavior. A Color Value discriminator never names or implies a
Color Profile.

Tile Index and tile transform flags are tile-domain values and are never variants of
Color Value.

A Background Color used by Layer conversion or Cel clearing is an explicit compatible
Color Value. SPA does not source it from an editor foreground/background color or
preference that is absent from the request.

## Consequences

- Agents can interpret a color or pixel value without relying on the active Sprite
  or decoding an implementation integer.
- Indexed artwork retains its authored Palette Index and transparent-index semantics.
- Results can expose both an Indexed pixel's native value and its resolved display
  color without conflating them.
- Cross-Color-Mode behavior becomes reproducible and testable at the public boundary.
- Operation schemas state which Color Value variants they accept instead of assuming
  every Aseprite color-bearing property has identical semantics.

## Rejected alternatives

### Normalize every pixel to RGBA

This loses the Palette Index that is the authored value of an Indexed Image and
conflates transparent-index behavior with alpha.

### Expose Aseprite packed pixel integers

Their encoding depends on Color Mode and active Sprite context, so they are not a
stable self-describing public value.

### Implicitly convert incompatible Paint colors

Nearest-color, grayscale, quantization, and dithering choices can change the result
and may depend on hidden preferences. Conversion must be declared.
