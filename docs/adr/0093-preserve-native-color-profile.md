# ADR-0093: Preserve native Color Profile assignment, conversion, and export

## Status

Accepted

## Context

Aseprite's editor uses **Color Profile** for the description attached to a Sprite's
stored colors. Its Lua API represents the same value with the `ColorSpace` type and
exposes two semantically different Sprite operations. Assign Color Profile changes
the profile without changing pixel or Palette values. Convert Color Profile transforms
applicable pixels and Palette Entries so the appearance is preserved in the target
profile, then assigns that profile. Color Profile is independent of RGB, Grayscale,
or Indexed Color Mode.

The public Lua constructor can create no profile, sRGB, or an ICC profile loaded from
a file. Aseprite File Formats differ in which profile forms they can encode. Export
can also depend on internal file-operation configuration derived from color-management
preferences, so leaving the behavior implicit makes the output environment-dependent.

A real headless Aseprite 1.3.18.5 probe changed
`app.preferences.color.manage` to `false` and observed that value, but PNG saving still
produced the same 87-byte file and SHA-256 as the `true` case; both contained the sRGB
chunk. The file operation therefore did not honor that script-time preference as a
usable export seam. In the same probe, assigning `ColorSpace()` before save produced a
PNG without a profile chunk. Assigning and converting to a DCI-P3 ICC file each
embedded an `iCCP` chunk, and the two PNGs had different SHA-256 values. Native Assign
and Convert are thus both usable and observably distinct in headless execution.

## Decision

- **Color Profile**, **Assign Color Profile**, and **Convert Color Profile** are
  canonical Aseprite terms in SPA's ubiquitous language. `ColorSpace` remains the
  native Lua API type used by the Kernel, not a competing public domain abstraction.
- Color Profile is independent of Color Mode. A request never uses one term as an
  alias for the other, and Color Value does not carry an implicit profile.
- SPA exposes `spa sprite assign-color-profile` as an explicit Sprite Mutation. Its
  target is `none`, `srgb`, or an exact ICC file. It invokes native Assign Color
  Profile and requires stored Image pixels and Palette Entries to remain unchanged.
- SPA exposes `spa sprite convert-color-profile` as a separate Sprite Mutation. Its
  target is `srgb` or an exact ICC file. It invokes native Convert Color Profile and
  reports every applicable changed Image and Palette. SPA does not promise additional
  coverage where the selected Aseprite runtime's native operation does not transform
  an object kind; Tileset behavior is specifically probed and reported.
- An ICC target contains an explicit file path. The file must exist, be readable, and
  load successfully through Aseprite's native `ColorSpace{ fromFile=... }` before
  mutation. Results include the input path, byte size, SHA-256, native profile name,
  and equality with the effective Sprite profile. Missing, unreadable, and invalid
  files are typed failures.
- Both Sprite operations use normal one-Sprite Mutation, Plan, and Target Commit
  semantics. They are not properties hidden under `sprite set` and do not create a
  general color-management, monitor-profile, or preference-management service.
- `spa export image` requires one `color_profile` Published Language branch:
  - `preserve` copies the Source Sprite's Color Profile, including explicit absence,
    to the disposable export Sprite;
  - `omit` assigns no profile to the disposable Sprite and changes no stored colors;
  - `assign` assigns an explicit `srgb` or ICC target without changing stored colors;
    and
  - `convert` applies native Convert Color Profile to an explicit `srgb` or ICC target
    on the disposable Sprite before encoding.
- Assign and Convert during export never mutate the Source Sprite. `omit` is the
  export expression of an absent output profile rather than an alias for a hidden
  global preference.
- Each stable File Format branch declares whether it can encode an absent profile,
  sRGB marker, or ICC profile. A request that the branch cannot represent fails before
  publication. SPA never silently omits an ICC profile, converts it into sRGB, or
  changes pixels to satisfy a format.
- The fixed Lua Kernel owns native Assign/Convert invocation, source-to-disposable
  profile transfer, and effective Sprite observations. ADR-0094 places Color Profile
  after rendering and before Palette preparation, Change Color Mode, and Background
  behavior. The Kernel does not rely on script-time mutation of
  `app.preferences.color.manage` for export. Python can validate ICC file facts and
  parse the produced File Format to verify encoded profile facts, but it never
  transforms colors, pixels, or Palettes.
- Results report source, requested, effective, and encoded Color Profile kind/name;
  ICC input facts where applicable; changed or unchanged Image and Palette facts;
  source immutability for export; and the final Artifact facts.
- Delivery tests distinguish Assign from Convert with color-sensitive fixtures;
  cover no profile, sRGB, and multiple valid ICC inputs; malformed inputs; RGB,
  Grayscale, Indexed, Alpha, Palette Changes, linked Cels, Tilesets, and native runtime
  coverage; standalone and Plan execution; every export branch; profile-aware and
  profile-unaware File Formats; source immutability; failure atomicity; and
  save/close/reopen or independent output-profile verification.

## Consequences

- SPA exposes Aseprite's complete public Color Profile intent without conflating it
  with Color Mode or display configuration.
- Exported appearance and metadata no longer depend on hidden working-profile or
  color-management preferences.
- Assign and Convert remain visibly different operations, including when composed
  into a non-mutating export.
- File Format slices must prove profile representation instead of treating successful
  file creation as sufficient evidence.

## Rejected alternatives

### Use Color Space as a second ubiquitous-language term

Aseprite's user-facing editor already calls the concept Color Profile. `ColorSpace`
is retained where the Lua API type itself is discussed.

### Read or set the working Color Profile preference

It introduces hidden environment state and the real headless probe showed that
script-time `color.manage` mutation did not control PNG output.

### Treat Assign and Convert as one operation

Assign preserves stored values and changes their interpretation. Convert changes
stored values to preserve appearance. Their results and risks are different.

### Implement ICC conversion in Python or Lua

That would duplicate Aseprite's native color-management semantics and make the
result depend on a second color engine.

### Let unsupported File Formats drop the profile

Silent omission changes how consumers interpret the same stored values and prevents
the agent from verifying its requested output.
