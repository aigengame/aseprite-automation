# Native Color Profile maintenance note

The Baseline Aseprite definition is `SPA_BASELINE_ASEPRITE_VESION` in
`src/spa/__init__.py`. It is a maintenance reference, not a compatibility guarantee.

## Current conversion boundary

Assign stores valid ICC metadata without converting colors. Convert admits only
complete-byte profile identities and directed pairs in
`src/spa/kernel/color/profiles/identities.json`. That file owns the current set;
this note does not repeat its hashes or maintain a second profile matrix. The
[redistributable profile record](issue-194-redistributable-profile.md) owns packaged
resource provenance. The packaged reference is CC0. A caller-supplied Apple
profile has a distinct identity and does not admit conversion to the CC0 identity
or the reverse. Tests use the CC0 resource and may explicitly supply the Apple input
for its separate identity checks.

Native `ColorSpace` construction does not establish conversion support. Native
backends can accept an ICC object and return success while only changing its label.
Profile header, matrix, TRC, name, and a successful conversion in one direction do
not establish support in the other direction. The finite identity/pair check avoids
inferring complete native support from those partial facts. Unlisted Assign inputs
remain valid under their independent metadata-storage contract.

Python validates ICC bytes with Pillow/LittleCMS and freezes the input bytes. Lua
loads that snapshot and checks Source identity and the directed pair against the
live Sprite. Earlier Assign/Convert Plan Steps update this private state, so later
Steps use the actual profile. Static Plan checks reject unlisted conversion targets;
opened Sources are checked at execution. Production uses no Python color transform.

## Persistence and native state

Aseprite can save None without a Color Profile chunk, then assign working sRGB when
batch loading that file. The bounded reader in `kernel/color/profile_file.lua`
restores encoded None before observation or conversion and rejects unsupported
encodings. Export uses the same reader on its disposable Sprite.

Save/reopen compares encoded profile kind, native equality, Image and Tile bytes,
and the complete Palette timeline. Assign preserves stored content. Convert reports
native content observations separately from profile changes; same-profile and
content-dependent no-ops remain valid. Counting changed pixels cannot prove or
replace conversion admission. Tileset observations do not imply that native Convert
transforms Tile colors.

## Runtime capability

Assignment and conversion have independent runtime checks. Conversion uses a
nontrivial RGB/Palette transform; constructor availability and same-profile no-ops
are insufficient. Baseline Aseprite built with `LAF_BACKEND=none` has no usable
native converter. The capability is withheld and conversion is refused before
publication, while Assign remains independently available. The actual selected
runtime observation governs admission; this is not a platform allowlist.

The relevant native backend returns no OS color spaces or converter through its
`CommonSystem` implementation. Its Release conversion path can copy Image values,
skip Palette transformation, and assign the requested profile. A headless display
alone does not determine converter availability; the compiled backend matters.

## Existing checks

`tests/color/test_e2e_color_profile.py` runs the public installed CLI and compares
independent native assignment/conversion with reopened stored pixels, Palette
Entries, links, Tilesets, encoded profile kind, input digests, and Source/Target
preservation. It checks that discovery agrees with converter availability and that
unsupported runtime conversion is refused. Conversion cases skip when the selected
runtime lacks the converter; those skips are not color-transformation coverage.

Plan tests cover live Source identity after Assign and conversion refusal without
publication. File-input tests distinguish validity, admitted identity/pair, and
persisted observations. These checks support the current boundary without claiming
arbitrary ICC support, identical native output across releases, or coverage on
unexecuted host configurations.
