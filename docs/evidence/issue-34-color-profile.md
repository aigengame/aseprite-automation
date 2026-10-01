# Native Color Profile evidence — issue #34

## Baseline and reproducible checks

Local macOS Aseprite 1.3.18.5-dev, Lua 5.4, API 41. Native source baseline:
[`v1.3.18.5`](https://github.com/aseprite/aseprite/tree/375989a61c3425cd4e8cdedfcfcca4bdfef7e1d9).
These observations do not establish Linux coverage or a cross-version certification.

`tests/color/test_e2e_color_profile.py` runs the public installed CLI. Its separate
Lua fixture invokes native assignment/conversion directly, then saves and reopens
the result. The assertions compare stored Image pixels, Palette Entries, links,
Tilesets, encoded profile kind, input digests, and Source/Target preservation.
The tests and probe use the fixed ICC files identified below. Production uses no
Python color transforms. Profile file validity, native admission, and persisted
observations are separate checks.

## Selected limited conversion set

The [owner decision](https://github.com/aigengame/aseprite-automation/pull/151#issuecomment-5922836235)
accepts limited support and refusal outside it, and reclassifies the former P1 as P2.
[#34](https://github.com/aigengame/aseprite-automation/issues/34) owns the selected
source/target matrix. The implementation uses full ICC byte equality against two
packaged files, then checks the directed pair. It does not classify arbitrary ICCs
by header, matrix, TRC, profile name, or successful native construction.

| Source Profile | Admitted Convert targets |
| --- | --- |
| Encoded None | Built-in sRGB |
| Built-in sRGB | Built-in sRGB; fixed linear-sRGB ICC |
| Fixed linear-sRGB ICC | Built-in sRGB; the same fixed linear-sRGB ICC |
| Fixed Display P3 ICC | Built-in sRGB; the same fixed Display P3 ICC |

Profile identities relative to `spa.kernel`:

| File | Bytes | SHA-256 |
| --- | --- | --- |
| `color/profiles/linear_srgb.icc` | 588 | `e8e39a911fbcba693d493fe2c7e33f68f76d360a3b38b3b6f7ea37dc43462e06` |
| `color/profiles/display_p3.icc` | 536 | `0ff6958f98684c61f6bbdce1368ddeaf3873baf84545baba482e920d92a914c0` |

The linear-sRGB file is the prior probe fixture, generated from LittleCMS sRGB by
replacing the shared parametric RGB TRC with gamma 1.0. Its fixed metadata is part
of the selected bytes. Display P3 is an unchanged copy of
`/System/Library/ColorSync/Profiles/Display P3.icc`, including its Apple copyright
metadata, and matches [#103's prior feasibility evidence](https://github.com/aigengame/aseprite-automation/issues/103#issuecomment-5846418098).
Tests pin that SHA-256 independently. The wheel inventory checks every packaged
ICC byte alongside the existing Lua and Sprite assets.

A different path with the same bytes is accepted. A metadata-only edit, another
sRGB/P3 encoding, or an unlisted pair is excluded even if that native transform
might work. This is the explicit cost of the finite set; expanding it requires
consumer evidence and a support decision. It does not narrow valid-ICC Assign.

The selected macOS runtime executes the three changing directions with Image and
Palette midtones. Standalone and live Plan outputs are compared with a separate
Lua fixture's direct native conversion and saved/reopened observations. The P3
sample `(180,70,30,127)` becomes `(195,60,2,127)` in sRGB, preserving alpha. Tests
cover an opened P3 Source and an earlier live Assign. Same-profile requests and
all-black content-dependent no-ops remain successful in both execution forms.
The runtime probe separately checks sRGB ↔ fixed linear-sRGB and fixed P3 → sRGB
Image/Palette transformations and persistence; version strings alone do not admit
conversion. See the Linux limitation below.

Refusal tests cover unlisted generated sRGB, a metadata-only P3 edit, an RGB LUT,
and the discontinuous curve from the investigation below. Each remains valid for
Assign but is refused as a Convert Source and Target. Tests cover opened Sources,
live Assign→Convert Plans, in-place execution, Step attribution, Source/Target byte
preservation, and cleanup. Five unlisted pairs between otherwise known profiles
are also refused. These tests establish the selected refusal boundary, not support
for converting every encoding in those families.

The compact test-only `tests/color/fixtures/rgb_lut.icc` is 584 bytes, SHA-256
`cbb97b160359f429be6a72208f0777c574920b8e88069d738714b648db1475c1`.
It was generated with LittleCMS: build linear-RGB→Lab16, use
`cmsTransform2DeviceLink(..., 4.3, cmsFLAGS_GRIDPOINTS(2))`, copy its A2B0 pipeline
into an sRGB profile, set class `scnr` and PCS `Lab `, and remove XYZ/TRC/chrm tags.
The smaller grid keeps this a compact refusal fixture; it is not the original LUT
file or the numeric oracle from the investigation.

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
stored Image/Palette values. Convert additionally requires the selected identity
and direction. Unlisted target files and pairs produce `color_profile_file_failed`
with `unsupported_profile` and `unsupported_conversion`; non-RGB targets retain the
static `unsupported_color_space` reason. Invalid and unreadable inputs remain typed
file failures. Lua loads the frozen snapshot through the native constructor before
mutation. The existing RGB validation is an early input check, not admission proof.

Adversarial review also reproduced native LAB-ICC Source to sRGB conversion that
only relabeled the profile: both the midtone Image and Palette stayed unchanged.
An independent LittleCMS check converted the sample `(48, 96, 144)` to `(0, 56, 20)`;
this is test evidence only, not a production transform. The initial non-RGB refusal
closed this case but did not establish admission for every RGB ICC. The selected
policy now refuses every unlisted Source ICC with `color_profile_source_unsupported`
before conversion. The encoded-profile reader retains the complete ICC bytes.
The native profile owner verifies their native equality with the loaded ColorSpace,
stores their identity, and updates that private state from frozen bytes after each
Assign/Convert. The header signature remains a failure detail, not an admission rule.
This covers opened Sources and Assign-then-Convert Plan Steps without a second color engine.
Tests verify the refusal preserves Source and Target, and that a later explicit
Assign of a supported RGB profile replaces the live source interpretation.

The result includes the requested path, byte size, SHA-256, native name, and equality
with the effective Sprite profile. Native names are observations and need not match
ICC description text. For example, the generated fixture's description is `sRGB
built-in`, while this runtime reports `Linear Transfer with sRGB Gamut`.

Plan Steps use the same native operation. Their receipts describe each Step's live
state; only the enclosing Plan claims final persistence. Failed Steps do not publish.
Runtime capability probes test assignment and real pixel/Palette conversion
separately; constructor availability or a same-profile no-op is insufficient evidence.

## Conversion admission investigation — PR #151

This section retains the technical investigation that preceded the owner decision.
It disproves the initial general admission rules. The selected finite set above
supersedes the earlier unresolved support decision; the following counterexamples
do not establish additional conversion requirements.

The reviewed head was `a3543118`. The independent preflight and receipt fixes at
`f42ca0a` do not change native admission. On the local macOS runtime above, both
standalone and Assign-then-Convert Plan execution reproduce false success for an
RGB input LUT profile (`scnr`, RGB, Lab PCS, A2B0, no XYZ/TRC tags). Native Assign
preserves the profile, but Convert to sRGB changes only its profile metadata.
Independent LittleCMS conversion maps `(48, 96, 144)` to `(119, 165, 198)`.
The input SHA-256 is
`de7ad2cb5bd96fdde6ad9f75c32542092baeaf6b35c5de4757d96068490021a0`.

The pinned LAF uses Skia `m124-08a5439a6b`.
[`SkColorSpace::Make`](https://github.com/aseprite/skia/blob/m124-08a5439a6b/src/core/SkColorSpace.cpp#L193-L225)
requires XYZ/TRC facts and a usable matrix; it cannot represent a LUT-only ICC.
An absent native color space is not surfaced as a Lua error:
[`SkColorSpaceXformSteps`](https://github.com/aseprite/skia/blob/m124-08a5439a6b/src/core/SkColorSpaceXformSteps.cpp#L23-L35)
substitutes sRGB for a null source and the source for a null target.
Lua `ColorSpace` exposes name and equality, not this native support state.

RGB plus an XYZ matrix and shared numerical TRCs is also insufficient. A second
experiment started from Pillow's generated sRGB ICC, retained its XYZ matrix, and
replaced all three shared `para` type 3 curves with `(g,a,b,c,d)=(2,1,0,0.25,0.5)`.
Pillow/LittleCMS accepts this encoding. The selected native runtime can use it as
a source, but its discontinuous curve fails the native target inverse check.

| Experiment, starting sample `(48, 96, 144)` | Native result | Independent LittleCMS result |
| --- | --- | --- |
| Generated ICC to sRGB | `(61, 86, 153)` | `(61, 86, 153)` |
| sRGB to generated ICC | `(48, 96, 144)`, success and ICC assigned | `(30, 119, 135)` |
| Continuous control, same curve with `c=0.5`, sRGB to ICC | `(15, 60, 135)` | `(15, 60, 135)` |

The counterexample tests the proposed admission assumption; it does not establish
a requirement to support this curve. Native
[`computeLazyDstFields`](https://github.com/aseprite/skia/blob/m124-08a5439a6b/src/core/SkColorSpace.cpp#L95-L112)
substitutes the sRGB inverse when
[`skcms_TransferFunction_invert`](https://github.com/aseprite/skia/blob/m124-08a5439a6b/modules/skcms/skcms.cc#L1859-L1969)
fails. Constructor success and source-direction success therefore do not prove
target-direction support.

A structural admission rule would also need evidence for full tag-table bounds,
duplicate tags, optional tags that cause parser rejection, LUT/matrix hybrids,
matrix inversion and finite arithmetic, and the actual native backend. These are
conditions of the pinned implementation, not a stable public Aseprite support API.
A release version string and one successful runtime fixture do not prove them
for all ICC inputs or other builds. Counting changed pixels cannot replace admission
because valid same-profile and content-dependent no-ops exist.

The proposed numerical-TRC restriction also excludes working inputs. The local
macOS system `sRGB Profile.icc` has three 1024-entry `curv` tables. Converting the
linear ICC fixture to this file succeeds, changes pixels, and produces the same
Image and Palette values as conversion to native built-in sRGB. This is an executed
example of the native approximate-sRGB table path, not a hypothetical compatibility
loss or a claim that every table profile works.

The initial matrix/shared-TRC proposal was rejected. The later owner decision accepts
limited support, now implemented by the positive set and directed pairs above.
Expanding rejection rules one counterexample at a time would retain the faulty
assumption that SPA can infer complete native conversion support from partial ICC
facts. Native support/failure reporting would address the missing signal directly;
adding such an API or changing the runtime is separate scope. Assign keeps its
independent valid-ICC storage contract throughout this investigation.

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
