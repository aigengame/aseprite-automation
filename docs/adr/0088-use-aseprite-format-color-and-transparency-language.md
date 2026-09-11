# ADR-0088: Use Aseprite File Format, Color Mode, and transparency language

## Status

Accepted

## Context

A typed `export image` request must prevent silent format, color, and transparency
loss. An earlier proposal named three possible concepts: Static Image Format, Color
Handling, and Alpha Handling. Those names do not accurately preserve Aseprite's
language.

Aseprite calls an encoder/decoder capability a File Format. Its public UI, errors,
C++ `FileFormat`, and plug-in `newFileFormat` API use that name and associate the
format with one or more filename extensions and supported image properties.
Aseprite calls RGB, Grayscale, and Indexed the Sprite's Color Mode and names the
native conversion command Change Color Mode (`ChangePixelFormat` in the scripting
API).

Aseprite has no single Alpha Handling concept. RGB and Grayscale Images use an Alpha
Channel. Indexed transparency instead involves the Sprite's Transparent Color Index
and can also involve alpha values on Palette Entries. Background Layer, Background
Color, and Convert to Background are the native concepts for making transparent or
missing areas opaque. Treating all of these as one Alpha policy would erase important
Color Mode differences.

The native save seam is also unsafe as an implicit policy. A real 1.3.18.5 headless
probe exported transparent and half-transparent red RGB pixels to JPEG as opaque red,
discarding Alpha rather than compositing with a Background Color. An Indexed-to-JPEG
request produced no file while `Sprite:saveCopyAs()` still returned `true` and the
process exited zero.

## Decision

- SPA reuses Aseprite's File Format as the export encoding concept. It does not add a
  canonical Static Image Format term. Within `export image`, the Descriptor accepts
  only File Format variants whose supported SPA slice produces one image file.
- The request explicitly declares `file_format` as a discriminated union. Each branch
  owns only that File Format's Aseprite-native options, such as a JPEG quality or a
  format-specific compression choice. There is no generic options dictionary or
  cross-format quality/compression abstraction.
- The Export Destination extension must match the declared File Format; recognized
  aliases such as `.jpg` and `.jpeg` are declared by that branch. Aseprite still
  selects its native encoder by the staged filename extension, but the extension does
  not become hidden public intent.
- SPA reuses the existing Color Mode term. The request's `color_mode` value is either
  a `preserve` branch or a `change` branch with one explicit target Color Mode and the
  applicable native Change Color Mode inputs. These branch names are Published
  Language choices, not new ubiquitous-language concepts.
- `preserve` cannot rely on Aseprite's warning-and-continue behavior. It is valid only
  when the File Format and actual selected output can preserve the applicable Color
  Mode and its required palette/color facts. An incompatible request fails before
  final publication.
- `change` executes Aseprite's native Change Color Mode against the disposable export
  Sprite. ADR-0089 through ADR-0092 define its exact RGB, Grayscale, Indexed,
  Dithering, Palette, RGB Map, grayscale, and fit inputs. It never mutates the Source
  Sprite.
- The request's `transparency` value is either `preserve` or `background` with one
  explicit fully opaque Background Color compatible with the effective export Color
  Mode. These are request branches, not an Alpha Handling domain concept.
- Transparency `preserve` succeeds only when no visible Alpha, Transparent Color
  Index, or applicable Palette Entry transparency fact required by the selected
  output would be lost. A File Format without transparency support can still encode
  an actually opaque result when verification proves that no transparency information
  is discarded.
- Transparency `background` applies Aseprite Background semantics to the disposable
  export Sprite with the explicit Background Color before native encoding. It never
  uses the editor's current background color, silently discards Alpha, or chooses a
  Palette Entry.
- Color Profile is an independent native concept defined by ADR-0093. `export image`
  requires an explicit `color_profile` branch so output cannot depend on hidden color
  management preferences. Each File Format branch declares which profile states it
  can encode and rejects an unrepresentable request.
- ADR-0094 fixes the internal order as render, Color Profile, optional Palette
  preparation, Change Color Mode, transparency/Background, and File Format encoding.
  Background Color is interpreted in the final Color Mode and effective Color Profile.
- The Python Application Layer owns the accepted `export image` use-case orchestration
  and constructs its private ordered execution. The fixed Lua Kernel owns native
  rendering, Change Color Mode, Background behavior, Assign/Convert Color Profile,
  and encoder invocation against the same disposable Sprite. Contract validation can
  reject structurally invalid branch combinations and the file adapter verifies
  extension and output facts, but Python implements no color conversion, alpha
  compositing, palette mapping, profile transform, or encoder.
- The Operation Result reports the declared File Format and extension, source and
  effective Color Mode, effective transparency/background facts, format-native
  options, and verified file facts. It must distinguish a valid opaque result from a
  lossy native warning path.
- Each supported File Format branch enters through an evidence-bearing vertical slice
  and stable schema. Its capability matrix independently declares the applicable file
  role and cardinality, extension aliases, native options, Color Modes, transparency
  representation, Color Profile states, and runtime constraints. No branch inherits
  support from another File Format. `spa info` reports only the matrix proven for the
  current SPA and Aseprite runtime; a runtime plug-in cannot dynamically enlarge the
  public schema.

## Consequences

- SPA's ubiquitous language remains anchored in Aseprite rather than adding three
  overlapping export abstractions.
- RGB/Grayscale Alpha and Indexed Transparent Color Index semantics stay distinct.
- Agents declare lossy Color Mode changes and Background application rather than
  inheriting headless warning behavior.
- File Format-specific options remain precise and independently evolvable.
- Color Profile assignment, conversion, omission, and preservation are explicit
  functional behavior rather than headless preference effects.
- ADR-0089 through ADR-0092 now define the shared Change Color Mode, Palette,
  color-mapping, and Dithering contracts instead of an unspecified conversion
  dictionary.

## Rejected alternatives

### Define Static Image Format

Aseprite already defines File Format. Single-image output is a constraint of
`export image`, not a second format concept.

### Define Color Handling

Aseprite already defines Color Mode and Change Color Mode. The preserve/change choice
is request structure, not a new creative-domain object.

### Define Alpha Handling

That name incorrectly treats RGB/Grayscale Alpha Channel, Indexed Transparent Color
Index, Palette Entry alpha, and Background conversion as one mechanism.

### Let the destination extension and native warnings decide

The real probe showed silent Alpha loss and truthy zero-exit failure. Those are not
reliable agent-facing semantics.

### Convert or composite in Python

That would duplicate Aseprite's Color Mode, Palette, Background, and encoder behavior
outside the fixed Lua Kernel.
