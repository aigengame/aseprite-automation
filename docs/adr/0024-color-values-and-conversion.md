# ADR-0024: Preserve Color Mode in public Color Values

## Status

Accepted

Feature issues own operation-specific contracts and acceptance.

## Context

Aseprite stores different native pixel values for RGB, Grayscale, and Indexed
Sprites. An Indexed pixel stores a Palette Index, and its Transparent Color
Index is not interchangeable with per-pixel alpha. A packed native integer has
no context-free meaning. Native conversion can also depend on result-affecting
mapping, quantization, fit, grayscale, or dithering choices.

## Decision

SPA publishes one discriminated **Color Value** family:

- `rgba` contains integer red, green, blue, and alpha components from 0
  through 255.
- `grayscale` contains integer gray and alpha components from 0 through 255.
- `palette-index` contains an existing Palette Index.

The discriminator is required. Packed native pixel integers and untagged
channel tuples are private implementation details.

An Indexed pixel's native value remains its Palette Index. A resolved RGBA
observation is separate and does not replace that value. The Sprite's
Transparent Color Index remains distinct from Alpha Channel semantics.

Operations accept Color Values compatible with the target Color Mode unless
they expose explicit native conversion inputs. SPA does not silently choose a
nearest color or read undeclared editor preferences. Sprite-wide conversion
uses Aseprite's native **Change Color Mode** capability rather than a parallel
conversion framework.

Color Mode remains independent of Color Profile. Tile Indexes and tile
transform flags are not Color Values. A Background Color is explicit request
data in the target Color Mode.

## Consequences

Public colors remain self-describing, Indexed artwork preserves its authored
indexes and transparency semantics, and result-affecting conversions are
reproducible across isolated invocations.

## Rejected alternatives

Normalizing every pixel to RGBA loses the authored Indexed value. Exposing
packed integers leaks Sprite context. Implicit conversion makes equal requests
depend on hidden policy.
