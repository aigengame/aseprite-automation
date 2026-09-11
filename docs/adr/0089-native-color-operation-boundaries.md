# ADR-0089: Define native color operation boundaries

## Status

Accepted

## Consolidates

- ADR-0090: separation of Color Quantization from Change Color Mode
- ADR-0091: explicit native color-mapping defaults
- ADR-0092: conditional native Dithering
- ADR-0093: native Color Profile assignment and conversion

The owning feature issues and Operation Descriptors hold exact request branches,
enumerations, result fields, runtime evidence, and acceptance matrices.

## Context

Aseprite provides several related but different native color operations. Change Color
Mode maps a Sprite between RGB, Grayscale, and Indexed representations. Color
Quantization creates Palette colors from rendered Sprite colors. Assign Color Profile
changes the interpretation attached to stored colors, while Convert Color Profile
transforms applicable stored colors to preserve appearance.

Native scripting inputs can also read editor preferences or silently replace missing,
unknown, or inapplicable values with defaults. SPA must preserve the native capabilities
without merging these operations or allowing hidden state to decide agent output.

## Decision

- SPA uses Aseprite's Color Mode, Change Color Mode, Color Quantization, Color Profile,
  Assign Color Profile, Convert Color Profile, RGB Map Algorithm, Color Best Fit
  Criteria, Dithering Algorithm, Dithering Matrix, and Dithering Factor concepts. Their
  canonical definitions belong to `CONTEXT.md`; SPA does not replace them with a generic
  color-processing framework.
- Change Color Mode is an explicit Sprite Mutation, not a generic property assignment.
  Standalone execution, Plan execution, and export composition invoke the same packaged
  Lua Kernel capability.
- Color Quantization is a separate Palette Operation. Change Color Mode to Indexed
  consumes already established Effective Palettes and never hides Palette generation,
  import, or editing inside conversion. An export can explicitly compose Palette
  preparation before conversion on its disposable Sprite.
- Color Profile is independent of Color Mode. Assign Color Profile and Convert Color
  Profile remain separate native operations because assignment preserves stored values
  while conversion changes applicable Image pixels and Palette Entries.
- Each Operation Descriptor exposes only inputs applicable to the actual native path.
  Result-affecting native choices are explicit. Omission is not equated with an explicit
  native `default`, and unknown, case-variant, numeric, cross-branch, or otherwise
  inapplicable inputs cannot reach Aseprite's preference or fallback behavior.
- A same-Color-Mode request is a valid idempotent no-op when it carries no inapplicable
  conversion input.
- Dithering is available only on native conversion paths where it has an effect. Matrix
  resolution must distinguish intentional native omission from a requested resource
  that failed to resolve; SPA never reports a silent fallback as the requested result.
- A Python environment adapter may resolve installed Dithering Matrix metadata and may
  validate or digest an ICC file. It does not interpret matrix pixels, quantize or map
  colors, transform profiles, or implement Dithering. Native color behavior and its
  effective observations remain in the fixed Lua Kernel.
- A standalone Sprite Mutation applies the applicable native operation to the complete
  Sprite and uses normal Target Commit semantics. Export applies the same packaged
  capabilities only to disposable export state and never mutates the Source Sprite.
- ADR-0094 owns the fixed `export image` composition order. File Format support is
  feature-specific and cannot silently omit a requested Color Profile, lose required
  transparency, or perform an undeclared conversion.
- Issues #32, #33, and #34 own delivery and acceptance for Color Quantization, Change
  Color Mode with mapping and Dithering, and Color Profile operations respectively.

## Consequences

- SPA retains Aseprite's distinct native operations and terminology instead of creating
  overlapping conversion abstractions.
- One Lua authority serves editable-Sprite and disposable-export use cases without
  requiring separate algorithms.
- Agents cannot mistake preference-derived or fallback behavior for declared intent.
- Palette generation, pixel representation change, and profile transformation remain
  independently composable and observable.

## Rejected alternatives

### Use one generic color-conversion request

It would hide materially different native side effects and create a bag of inputs that
many execution paths ignore.

### Treat omitted or unknown inputs as native defaults

Native code can read mutable preferences or silently map invalid values to a different
operation, making the result differ from the request.

### Generate a Palette inside Change Color Mode

Aseprite exposes Color Quantization separately, and implicit generation would destroy
or bypass deliberate Palette choices.

### Implement mapping, Dithering, quantization, or profile conversion outside Aseprite

That would introduce a second color engine and violate the Lua Operation Kernel's
authority over core Aseprite behavior.
