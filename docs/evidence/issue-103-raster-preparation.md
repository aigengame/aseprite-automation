# Frozen raster preparation — issue #103

## Delivered boundary

`spa raster prepare` composes existing native Raster, Palette, Color Mode, and
Color Profile owners and the existing staged PNG publication scope. It consumes
frozen input bytes once, prepares one PNG, verifies the complete staged output,
and publishes only after the declared facts agree. It adds no Plan Step, recipe
engine, pixel matcher, resampler, generation provider, or input registry.

The accepted matrix is single-frame 8-bit RGB/RGBA PNG input and either RGBA or
Indexed PNG output. Truly untagged input explicitly assumes sRGB; encoded sRGB
keeps its meaning; the existing supported RGB ICC identities require native
conversion. Thresholding follows normalization. Both encoded outputs have sRGB
intent 0 and no retained ICC. Unsupported or ambiguous metadata rejects.

The result's `reproduction` record contains the source byte size/SHA-256,
Specification, resolved geometry and anchors, native versions and effective
mapping choices, Profile treatment, Palette, and hashes of complete decoded
RGBA/stored content. Reproduction requires that retained record; a new output
path is permitted. This record has no registry or cross-runtime compatibility
promise and does not evaluate artistic quality.

## Reproducible checks

From an installed checkout environment:

```sh
uv run --frozen --group test pytest tests/preparation -m "not e2e"
SPA_TEST_ASEPRITE=/absolute/path/to/aseprite \
  uv run --frozen --group test pytest tests/preparation -m e2e --durations=10
SPA_TEST_ASEPRITE=/absolute/path/to/aseprite \
  uv run --frozen --group test pytest tests/export tests/runtime -m e2e
```

Recorded locally on 2026-10-03: macOS, Python 3.13.13, Aseprite 1.3.18.5-dev,
Lua 5.4, API 41. The installed CLI resolves to the current feature checkout.

| Evidence | What it establishes |
| --- | --- |
| 76 fast public-dispatch cases | Strict input/Palette/Point admission, all rounding choices and actual resize ratios, outside anchors, final Point bounds after placement, changed or missing input, mismatched Specification/runtime/content, malformed native evidence, complete PNG/sidecar verification, overwrite/alias checks, rechecked source alias, and publication failure cleanup. |
| 19 installed-CLI native cases | RGB/RGBA input; threshold 1/128/255 and hidden RGB; empty explicit crop; automatic bounds; exact and scaled nearest resize; full pixel placement; transparent Palette indices 0/7/255 including 256 entries; unused/duplicate entries; exact PLTE/tRNS; RGBA/Indexed pixel parity; sRGB intent 3 normalization; native P3 conversion; wizard preparation and reproduction. |
| 6 native preference cases | In one process, contrasting profile/working-space/quantization preferences yield identical requested/effective facts and complete output pixels. Active document/colors and preferences are restored after success and a refused native input. |

The wider-gamut counterexample starts with Display P3 RGB `(180,70,30)` and a
Palette containing both that value and `(195,60,2)`. Native conversion selects the
latter; untagged/sRGB select the former. Both modes independently decode to those
expected pixels. Alpha 127/128 demonstrates threshold order, while the handler
checks every original alpha byte against the normalized native Image before
thresholding. The source PNG bytes remain unchanged.

The independent small raster uses literal complete pixel expectations. Palette
tests verify every encoded entry, even unused entries, and resolve every stored
index against that Palette. Duplicate-color winner indices are deliberately not
fixed; native mapping owns that choice. The wizard test reads only the existing
frozen input and declared Palette, not the example's Python matcher or preparation
algorithm. Its 1060×1484 input becomes 133×186, placed at `(17,33)` on a 224×224
Canvas; reported foot/gem anchors are `(84,212)` and `(123,59)`. A second request
reproduces the retained record and complete decoded content.

## Cost and platform limits

The first 18-case CLI matrix took **29.59 s** locally. The full wizard preparation
and reproduction pair accounted for **7.93 s**; this includes two CLI invocations,
native probes, frozen-byte transport, transformations, independent decoding, and
publication. A later concurrent regression run measured that pair at **8.41 s**.
The additional RGB input case passed in a separate **1.26 s** pytest run. These
are observations for this fixed workload, not throughput or CI timing guarantees.

The preparation cases run in batch without a window. The preference fixture uses
native editor state in that batch process; it is not windowed UI acceptance.
Linux Native E2E was **not dispatched** for this work. The existing Linux build's
missing Color Profile converter is an explicit capability refusal for ICC input;
the committed tests exercise that public refusal when the capability is absent,
while untagged/sRGB cases retain the normal native path. macOS conversion success
does not establish Linux conversion support.
