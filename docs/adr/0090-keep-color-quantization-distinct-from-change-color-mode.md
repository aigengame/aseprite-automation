# ADR-0090: Keep Color Quantization distinct from Change Color Mode

## Status

Accepted

## Context

Aseprite exposes **Change Color Mode** (`ChangePixelFormat`) and **Create Palette
from Current Sprite (Color Quantization)** (`ColorQuantization`) as separate native
commands. `ChangePixelFormat` does not generate a Palette. When converting to Indexed,
it maps each Cel Image through the Effective Palette for that Cel's Frame; the native
Tileset path uses the first Frame's Palette.

`ColorQuantization` renders every Frame of the Sprite, generates a Palette value, and
applies that value to the Current Palette selected by the active Frame. In headless
mode, `useRange=false` means replacing the complete current Palette rather than
limiting the replacement to selected Palette Entries. It does not create a Palette
Change: the underlying `SetPalette` command mutates the Palette already effective at
the selected Frame. `useRange=true` depends on mutable Palette Picks and is therefore
not a suitable agent contract.

The command also reads Aseprite's `experimental.new_blend` preference when rendering
the Sprite for quantization. That is a result-affecting native input, not a reason to
build a general preference-management subsystem.

A real Aseprite 1.3.18.5 headless probe set the preference to both `false` and `true`
through `app.preferences.experimental.new_blend`, restored its original value, and
then quantized a two-color Sprite. The operation retained one Palette Change and
produced a Palette of size two. The native input is therefore controllable through
the fixed Lua Kernel.

## Decision

- **Color Quantization** is the canonical Aseprite operation term. **Current Palette**
  names the Palette shown for the active Frame in the editor; SPA addresses the same
  persisted value deterministically as an Effective Palette or exact Palette Change.
  **Palette Source** is not added to the ubiquitous language.
- `spa sprite change-color-mode` to Indexed consumes the Sprite's already established
  Effective Palettes. It does not generate, import, or otherwise prepare a Palette.
  The operation reports the Palette Change used for every converted Image. Native Cel
  Images use the Palette effective at their Frame, while Tileset Tile Images use the
  first Frame's Palette and report that basis.
- A caller that needs different Palette content composes an explicit Palette
  Operation before Change Color Mode. Palette Import and Palette Set retain their
  existing meanings; Color Quantization is exposed as the separate
  `spa palette color-quantization` Operation.
- `spa palette color-quantization` targets one exact existing
`palette_frame_number`. The Lua Kernel activates that Frame, clears Palette Picks,
sets the requested New layer blending method, and invokes native `ColorQuantization`
with `useRange=false`. It quantizes the native rendering of every Sprite Frame and
replaces the complete addressed Palette value; it cannot create or delete a Palette
Change.
- Its request requires `max_colors` in `1..256`, explicit `with_alpha`, an explicit
  RGB Map Algorithm of `default`, `rgb5a3`, or `octree` as defined by ADR-0091, and
  the native `new_layer_blending_method` boolean. It rejects omitted, unknown,
  numeric, and case-variant algorithm values, Frame/Tag/Layer/Selection scopes,
  `useRange`, Palette Picks, and unknown or ignored fields. `max_colors` is a limit;
  the result reports the actual Palette size and complete Entries rather than
  assuming the requested limit was filled.
- The Operation reports the addressed Palette Change, its Effective Frame Range,
  source rendering scope, requested and actual color counts, Alpha choice, algorithm,
  effective algorithm, New layer blending method, complete resulting Entries, and
  every Frame whose rendering can change. Normal staged Target Commit and
  save/close/reopen verification apply.
- When `export image` changes its disposable one-Frame Sprite to Indexed, Palette
  preparation is an explicit export step outside the shared Change Color Mode
  request. The export request can copy the selected source Frame's Effective Palette
  or invoke the same fixed Color Quantization handler on the rendered disposable
  Sprite after the Color Profile branch. It reports the chosen native preparation and
  resulting Palette before invoking the shared Change Color Mode handler. ADR-0094
  fixes that order; no hidden quantization occurs.
- Additional Palette preparation capabilities can be composed as native Palette
  Operations without changing Change Color Mode semantics.
- The fixed Lua Kernel is the authority for Current/Effective Palette resolution,
  native Color Quantization invocation, complete Palette replacement, temporary
  active-Frame, Palette-Pick, and New layer blending method state, restoration, and
  observations. Python neither quantizes colors nor assembles temporary Lua
  implementations. The proven preference seam is private to this operation and does
  not introduce a general preferences model or service.
- Runtime tests cover RGB, Grayscale, and Indexed source Sprites; visible Layer and
  Blend Mode composition; all Frames; all three requested algorithms including
  `default` resolving to Octree; every color-count boundary; Alpha and transparency;
  exact Palette Change targeting; multiple Palette Changes; both New layer blending
  method values; Palette-Pick and active-Frame perturbation; no change-point creation;
  failure restoration; export source immutability; and save/close/reopen evidence.

## Consequences

- Change Color Mode remains one native conversion operation instead of becoming a
  palette-generation workflow.
- Agents can explicitly prepare a Palette and then convert, while `export image` can
  perform the same ordered native steps on disposable state in one request.
- Current Palette UI state is translated into an exact persisted Palette address;
  active editor state never becomes the public target.
- The result-affecting New layer blending method is explicit and locally restored
  without turning Aseprite preferences into a public subsystem.

## Rejected alternatives

### Define a generic Palette Source abstraction

It obscures the distinct native operations—using an existing Palette, importing or
editing one, and Color Quantization—and encourages hidden preparation inside Change
Color Mode.

### Always quantize before conversion to Indexed

Aseprite does not do this, it destroys deliberate Palette choices, and it makes
Change Color Mode broader than the native operation.

### Expose `useRange`

The native headless path interprets it through mutable Palette Picks rather than a
declared Frame or pixel range, making the result depend on editor state.

### Reimplement quantization in Lua or Python

That would create a second color algorithm authority and violate the Lua Kernel DRY
rule even if it reproduced one observed Aseprite version.

### Build a preference-management subsystem

The blend-method input is specific to native Color Quantization and is controllable
through the fixed Lua Kernel. A general preference service would add unrelated
non-functional complexity.
