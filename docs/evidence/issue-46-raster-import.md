# Compatible PNG import evidence

Issue [#46](https://github.com/aigengame/aseprite-automation/issues/46) owns the
delivery contract. `spa image import` implements its bounded empty-Cel insertion
through the existing native mutation and Target Commit path.

## Independent input and native insertion

`spa.adapters.png_input` verifies PNG signature, chunk structure/order/CRC, encoded
8-bit RGB/RGBA/Indexed samples, palette/transparency definitions, and complete zlib
scanlines before accepting Pillow's decoded pixels. Pillow owns unfiltering and
Adam7 reconstruction. The separate checks are necessary: decoder tolerance can
otherwise accept truncated streams or reduce encoded 16-bit samples. APNG and
other formats are refused rather than selecting a frame or converting a format.

The use case reads the raster once. Its SHA-256 receipt and independent decoded
pixels describe those bytes. The fixed Kernel handler writes and loads a private
PNG copy, compares native stored content and full RGBA with the independent input,
and copies its Image with native `Sprite:newCel` only after exact empty-slot and
compatibility checks. It saves, closes, reopens, compares again, and reports the
persisted facts. Placement never clips the stored Image to the Sprite Canvas.

Real-runtime tests read imported pixels back through the installed `image get`
operation. They also change the original file between observation and native
execution: insertion and the receipt continue to describe the original frozen
bytes, while SPA leaves the later external file version untouched.

## Indexed meaning

Tests compare both original stored indexes and full RGBA. The destination's
Effective Palette is resolved at the selected Frame using the existing Color and
Palette owner. Only used indexes must match; differing unused colors, Palette
lengths, and unused mask indexes are accepted.

The following are distinct native cases, exercised with Aseprite 1.3.18.5 on local
macOS and included in the Linux native suite:

- An opaque source index can survive native PNG loading as a Background pixel,
  then become transparent in a regular destination Layer with the same mask index.
  Preflight refuses that destination.
- Native PNG loading can itself change partial alpha or hidden RGB when the PNG
  transparent entry becomes the native mask. Comparing only two native renders
  misses this loss; comparison with independently decoded pixels refuses it.
- A non-mask partial-alpha entry is accepted when complete RGBA remains equal.
  Multiple transparent entries are also accepted when all used pixels retain
  their literal meaning; entry count alone does not determine compatibility.
- Frame-varying Palettes can admit a PNG at Frame 2 while refusing it at Frame 1.

Neither source nor destination Palette is rewritten to make an input pass.

## Color Profile scope

The encoded input determines interpretation. The shared Profile helper assigns
that declaration without channel conversion when native load defaults obscure
None. Destination Profile and input Profile must match:

| Input metadata | Accepted identity |
| --- | --- |
| No encoded color definition | None |
| Valid sRGB, optionally accompanied by the standard matching gAMA/cHRM values | sRGB |
| Valid iCCP whose complete bytes match an admitted [Color Profile identity](../../src/spa/kernel/color/profiles/identities.json) | The same ICC identity |

Admission does not require a bundled reference. The current packaged references
are `linear_srgb` and `display_p3_cc0`; `display_p3` remains available only from
caller-supplied bytes. See the [#194 replacement evidence](issue-194-redistributable-profile.md)
for this resource change and its validation. Earlier #46 runtime receipts remain
historical evidence for their tested inputs.

An unlisted ICC, conflicting sRGB metadata, standalone gAMA/cHRM, ICC combined
with gAMA/cHRM, cICP, mDCV, cLLI, and eXIf are refused. These exclusions are the
current supported metadata policy, not a claim that every excluded combination
is invalid PNG. Invalid encodings also fail. No arbitrary ICC equivalence or
profile inference is provided. Existing Profile operations remain the owner of
explicit conversion.

## Publication and evidence boundaries

The Python use case verifies response geometry, addresses, defaults, independence,
content digests, and Profile against the request and decoded input. Indexed basis
is cross-checked with the returned persisted Palette timeline and Transparent
Color Index. The native handler compares unrelated document facts and stored
Images using existing Profile persistence observations before saving and after
reopening. The result does not claim the native Image is an Artifact.

Focused regressions cover malformed or unsupported input, occupied and linked
slots, unsupported Layers, missing Frames, mismatched modes/profiles, source-file
preservation, frozen input identity, contradictory native evidence, changed raster
aliases, publication failure, and staging cleanup. Existing Source/Target identity
and In-place Mutation rules still apply. Concurrent writers between the final
identity check and publication are outside the existing Target Commit contract.

## Reproduction and coverage

- `tests/import/test_unit_png_input.py`: independent encoded facts and decoding.
- `tests/import/test_integration_image_import.py`: public schema, discovery,
  typed input failures, and absence of mutation for invalid requests.
- `tests/import/test_e2e_image_import.py`: installed CLI and native compatibility
  matrix, full pixels, profiles, placement, and independent Image relationships.
- `tests/import/test_e2e_import_boundaries.py`: real native evidence and publication
  boundaries, including file changes and injected commit failures.
- `tests/import/test_e2e_import_context.py`: changed editor Profile preferences,
  active document restoration, an error inside the insertion transaction, and
  actual reopened pixel corruption refused before publication.

Run with the repository's declared `SPA_TEST_ASEPRITE` configuration. These are
headless batch tests, without a graphical display. Local macOS evidence and Linux
CI evidence are separate executions; a local pass does not establish Linux results.
