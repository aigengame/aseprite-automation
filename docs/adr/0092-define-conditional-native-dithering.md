# ADR-0092: Define conditional native Dithering for Change Color Mode

## Status

Accepted

## Context

Aseprite's Change Color Mode command exposes three related native inputs when
converting RGB to Indexed: **Dithering Algorithm**, **Dithering Matrix**, and
**Dithering Factor**. The scripting/API algorithm values are `none`, `ordered`,
`old`, and `error-diffusion`. Ordered and Old Dithering use a matrix. Error Diffusion
uses Aseprite's Floyd-Steinberg implementation and scales its propagated error by a
factor; it does not use the supplied matrix. No Dithering input affects the native
Grayscale-to-Indexed path.

The native command's flat parameter bag accepts combinations it later ignores. It
also maps an unknown algorithm to `none`. A matrix string is first resolved as an
installed extension matrix ID and otherwise treated as a Sprite file path; missing or
failed resolution emits a diagnostic and silently falls back to Bayer 8-by-8. An
omitted matrix intentionally uses that same fixed native default. The bundled Bayer
matrices are ordinary installed Dithering Matrix resources with IDs `bayer2x2`,
`bayer4x4`, and `bayer8x8`, not separate algorithms.

Aseprite's Lua API can invoke the operation but does not enumerate installed
Dithering Matrix resources. SPA therefore needs an agent-facing request that retains
both native matrix sources while distinguishing successful resolution from fallback.
Runtime-resource discovery is environment adaptation, not ownership of Dithering
semantics.

## Decision

- **Dithering Algorithm**, **Dithering Matrix**, and **Dithering Factor** are canonical
  Aseprite terms in SPA's ubiquitous language. SPA does not create a generic
  resampling, noise, diffusion, or quantization framework around them.
- RGB-to-Indexed Change Color Mode requires exactly one conditional `dithering`
  branch:
  - `{ algorithm: "none" }` accepts no Matrix or Factor;
  - `ordered` and `old` accept an optional `matrix`, represented as either one exact
    installed Dithering Matrix ID or one explicit matrix file path, and accept no
    Factor; and
  - `error-diffusion` requires a finite `dithering_factor` in the inclusive native
    `0..1` range, accepts no Matrix, and uses Aseprite's native Floyd-Steinberg
    implementation.
- Omitting `matrix` for `ordered` or `old` explicitly preserves the native Bayer
  8-by-8 default. This is not an unknown-ID fallback. Results report `bayer8x8` as the
  effective matrix and identify that it came from the native default.
- An explicit Matrix address preserves the two native sources as a typed Published
  Language choice: an installed resource carries its exact ID, while a file resource
  carries its exact path. Installed IDs must resolve uniquely in the effective
  Aseprite runtime. Matrix files must exist, be readable, and satisfy Aseprite's native
  matrix-loading requirements. Resolution is completed before mutating the Sprite.
- The exact algorithm strings are `none | ordered | old | error-diffusion`. Missing
  branches, unknown or case-variant values, numeric enums, cross-branch fields,
  unresolved or ambiguous IDs, unreadable or invalid files, and non-finite or
  out-of-range Factors fail before conversion. SPA never allows an invalid request to
  become `none` or silently fall back to Bayer 8-by-8.
- Grayscale-to-Indexed rejects Dithering entirely because Aseprite ignores it. Other
  source/target pairs retain ADR-0089's prohibition on inapplicable conversion fields.
- A Python environment adapter may discover installed Dithering Matrix metadata and
  resolve an exact resource for the request. It does not interpret matrix pixels,
  select an algorithm, perform quantization, or implement Dithering. The fixed Lua
  Kernel remains the authority for matrix loading, typed-to-native mapping, native
  Change Color Mode invocation, and effective observations.
- Results report requested and effective Dithering Algorithm; requested Matrix source
  and address, resolution outcome, effective identity, and dimensions when applicable;
  Dithering Factor when applicable; the Effective Palette basis; and affected Sprite
  conversion facts. A successful result cannot represent a matrix-resolution warning
  followed by native fallback.
- The same descriptor definition and fixed Lua handler serve standalone
  `sprite change-color-mode`, Plan execution, and `export image.color_mode.change` on
  the disposable export Sprite.
- Delivery tests cover all four algorithms; omitted and explicit Bayer matrices;
  installed custom and file matrices with orientation-sensitive fixtures; Factors at
  `0`, `1`, and representative interior values; every invalid conditional combination;
  unknown/ambiguous/disabled IDs; missing, unreadable, and invalid files; RGB versus
  Grayscale source behavior; preference perturbation; standalone/Plan/export parity;
  failure atomicity; and save/close/reopen observations. Native parity tests prove SPA
  did not reproduce the Dithering algorithms.

## Consequences

- SPA preserves every native Change Color Mode Dithering algorithm and both native
  Matrix-addressing routes.
- Agents cannot accidentally pass ignored fields or mistake an Aseprite fallback for
  the requested matrix.
- Runtime discovery stays an adapter responsibility subordinate to the functional
  operation; it does not become an extension-management or security subsystem.
- The RGB-to-Indexed Change Color Mode contract is no longer gated on a Dithering
  follow-up decision.

## Rejected alternatives

### Mirror Aseprite's flat parameter bag

It accepts semantically irrelevant combinations and makes ignored Matrix or Factor
fields look effective.

### Support only bundled Bayer matrices

That would turn an implementation shortcut into a product restriction even though
Aseprite accepts installed extension matrices and matrix files.

### Let unknown matrices fall back to Bayer 8-by-8

It makes a typo or unavailable resource indistinguishable from intentional omission
and reports success for a different visual operation.

### Implement Dithering in Lua or Python

That would duplicate Aseprite's core operation semantics and violate the Lua Kernel's
role as a native-operation adapter rather than an alternate renderer.

### Accept Dithering for Grayscale-to-Indexed

The native conversion path ignores it, so accepting the request would claim control
that SPA and Aseprite do not exercise.
