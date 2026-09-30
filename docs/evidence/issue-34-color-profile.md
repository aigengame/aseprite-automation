# Native Color Profile evidence — issue #34

## Baseline and reproducible checks

Local macOS Aseprite 1.3.18.5-dev, Lua 5.4, API 41. Native source baseline:
[`v1.3.18.5`](https://github.com/aseprite/aseprite/tree/375989a61c3425cd4e8cdedfcfcca4bdfef7e1d9).
These observations do not establish Linux coverage or a cross-version certification.

`tests/color/test_e2e_color_profile.py` runs the public installed CLI. Its separate
Lua fixture invokes native assignment/conversion directly, then saves and reopens
the result. The assertions compare stored Image pixels, Palette Entries, links,
Tilesets, encoded profile kind, input digests, and Source/Target preservation.
The tests generate a linear-light RGB ICC from LittleCMS's sRGB profile by changing
the shared RGB parametric tone-response curve to gamma 1.0. Production uses no Python
color transforms. The packaged probe has a fixed copy of this generated profile.

## Assignment and conversion

The public Aseprite API provides
[`Sprite:assignColorSpace` and `Sprite:convertColorSpace`](https://github.com/aseprite/api/blob/main/api/sprite.md).
The native implementation's `ConvertColorProfile` visits unique Cels and all applicable
Palettes. It skips Tilemap Images and Grayscale Palettes; see
[`convert_color_profile.cpp`](https://github.com/aseprite/aseprite/blob/375989a61c3425cd4e8cdedfcfcca4bdfef7e1d9/src/app/cmd/convert_color_profile.cpp#L160).

| Tested input and operation | Cel Image values | Palette Entries | Tileset values |
| --- | --- | --- | --- |
| Assign None, sRGB, or RGB ICC | Unchanged | Unchanged | Unchanged |
| Assign LAB ICC | Unchanged | Unchanged | Not in this case |
| RGB Convert sRGB to linear RGB ICC | Changed | Changed | Unchanged on this baseline |
| Grayscale Convert sRGB to linear RGB ICC | Gray changes; alpha preserved | Unchanged | Not in this case |
| Indexed Convert sRGB to linear RGB ICC | Stored indexes unchanged | Changed | Not in this case |
| Convert sRGB to sRGB; None to sRGB | Unchanged | Unchanged | Not in this case |

Linked Cels remain linked after conversion and save/reopen. Image object IDs can
change even for a same-profile conversion, so result changes use stored-content
FNV-1a-64 digests, not transient IDs. Image observations use each Cel address;
linked Cels therefore have separate address observations of the shared Image.
Palettes report every change point and the zero-based changed Entry indexes.
Tilesets report each one-based Tileset index and each zero-based Tile index.
An unchanged Tileset report is a native observation, not a claim of converted colors.

## Encoded None and batch loading

Aseprite omits the Color Profile chunk when it saves None. Its batch `app.open()`
then assigns the working sRGB profile to such files. Changing Lua color preferences
did not change that behavior: the batch loader uses `FileOpConfig` defaults instead
of `fillFromPreferences()`. See
[`FileOp`](https://github.com/aseprite/aseprite/blob/375989a61c3425cd4e8cdedfcfcca4bdfef7e1d9/src/app/file/file.cpp#L1456)
and the [profile encoder](https://github.com/aseprite/aseprite/blob/375989a61c3425cd4e8cdedfcfcca4bdfef7e1d9/src/dio/aseprite_encoder.cpp#L764).

The existing Export path already read this encoded fact and restored native None
on its disposable loaded Sprite. That bounded reader now lives in
`kernel/color/profile_file.lua`, shared by Export and Color Profile operations.
It rejects gamma-tagged or unsupported profile encodings. Assign/Convert restores
None only when the file declares None, before observing or transforming colors.
The final save/reopen gate checks the encoded kind, native equality, all Image and
Tile bytes, and the complete Palette timeline. It refuses publication on a mismatch.

## ICC input evidence

Native `ColorSpace{fromFile=...}` accepted both empty bytes and arbitrary text as
unnamed ICC objects. Constructor success alone does not validate a profile.
Python therefore validates ICC bytes with the existing Pillow/LittleCMS dependency
and snapshots the exact bytes. Assign accepts valid ICC metadata, including tested
LAB ICC; native assignment and save/reopen preserve its profile equality and all
stored Image/Palette values. Convert currently requires an RGB ICC target;
this conversion constraint does not narrow assignment. Unsupported conversion
targets, invalid files, and unreadable inputs produce typed `color_profile_file_failed` results.
Lua loads the snapshot through the native constructor before mutation.

The result includes the requested path, byte size, SHA-256, native name, and equality
with the effective Sprite profile. Native names are observations and need not match
ICC description text. For example, the generated fixture's description is `sRGB
built-in`, while this runtime reports `Linear Transfer with sRGB Gamut`.

Plan Steps use the same native operation. Their receipts describe each Step's live
state; only the enclosing Plan claims final persistence. Failed Steps do not publish.
Runtime capability probes test assignment and real pixel/Palette conversion
separately; constructor availability or a same-profile no-op is insufficient evidence.

## Linux CI build limitation

The current `scripts/build_aseprite.sh` selects Release with `LAF_BACKEND=none`.
At the pinned LAF revision, Linux selects `SystemX11`, which inherits the
[`CommonSystem` color stubs](https://github.com/aseprite/laf/blob/ec6f2a5166142c7bf789452a2cbbd18ff4782840/os/common/system.h#L64).
These return no OS color spaces or converter. Aseprite's Release conversion path
then copies Image values, skips Palette transformation, and assigns the target
profile. This is source evidence for the expected CI limitation, not a Linux
execution result. A headless display alone does not determine converter availability;
the compiled backend does.

The probe's nontrivial RGB/Palette conversion withholds
`aseprite_convert_color_profile` on such a runtime. Discovery emits the existing
Capability Gap; standalone and Plan conversion refuse with `runtime_incompatible`
before publication. Assignment remains independently available. Conservative Plan
discovery also omits `plan run` until every eligible Step capability is available;
direct Plans containing only supported Steps still execute.

The E2E suite checks that discovery agrees with the probe and exercises rejection
on a runtime without conversion. Conversion-specific cases explicitly skip there;
they must execute on the selected macOS bundle. These skips do not establish Linux
color-transformation coverage. Upgrading the Linux build backend is separate work.
