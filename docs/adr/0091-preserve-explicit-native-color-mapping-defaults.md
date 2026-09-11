# ADR-0091: Preserve explicit native color-mapping defaults

## Status

Accepted

## Context

Aseprite names two separate Indexed mapping choices: **RGB Map Algorithm** and
**Color Best Fit Criteria**. `ChangePixelFormat` accepts both. `ColorQuantization`
accepts RGB Map Algorithm because it uses the same native algorithm family while
generating a Palette, but it does not accept Color Best Fit Criteria.

The native UI exposes `Default (Octree)` as an RGB Map Algorithm and
`Default (Euclidean)` as a Color Best Fit Criteria. Source inspection shows that an
explicit RGB Map Algorithm `default` deterministically selects the Octree
implementation, including inside Color Quantization. Explicit Color Best Fit Criteria
`default` selects Aseprite's established `Palette::findBestfit` behavior, which is a
real native choice distinct from `rgb`, `linearizedRGB`, `ciexyz`, and `cielab`.

This differs from omitting a `ChangePixelFormat` field. An omitted RGB Map Algorithm
or Color Best Fit Criteria is taken from mutable editor preferences. It also differs
from an invalid value: Aseprite 1.3.18.5 parses unknown strings as the corresponding
`DEFAULT` enum and accepts numeric enum values. SPA must distinguish the explicit
native choice from those implicit fallbacks before invoking Aseprite.

## Decision

- **RGB Map Algorithm** and **Color Best Fit Criteria** are canonical Aseprite terms
  in SPA's ubiquitous language. SPA does not replace them with a generic distance,
  palette policy, quantizer, or color-mapping framework.
- The shared `rgb_map_algorithm` Published Language field is the exact documented
  string union `default | rgb5a3 | octree`. It is required wherever an Operation
  exposes RGB Map Algorithm. `default` is an explicit value, not omission. Results
  report both the requested value and effective algorithm; Aseprite 1.3.18.5 resolves
  `default` to `octree`.
- The shared `color_best_fit_criteria` Published Language field is the exact
  documented string union `default | rgb | linearizedRGB | ciexyz | cielab`. It is
  required for Change Color Mode to Indexed and any other delivered Operation whose
  native seam exposes Color Best Fit Criteria. `default` remains the native criteria
  value rather than being renamed or falsely equated with another enum member.
- `spa palette color-quantization` accepts all three RGB Map Algorithm values and
  does not accept Color Best Fit Criteria. `spa sprite change-color-mode` to Indexed
  accepts both shared values. The disposable export path reuses those same contracts.
- Missing fields, unknown strings, alternate spellings, case variants, numeric enums,
  and operation-inapplicable fields fail schema or semantic validation before Lua
  invocation. SPA never lets Aseprite turn an invalid value into `DEFAULT` or obtain
  an omitted value from preferences.
- One descriptor-owned enum definition and one fixed Lua Kernel mapping serve every
  Operation that exposes each concept. Operation schemas reference the shared
  definition rather than copying lists or parsers.
- Runtime results include the requested and effective RGB Map Algorithm, requested
  Color Best Fit Criteria where applicable, exact Effective Palette facts, and the
  resulting Palette Index observations. Python does not calculate a replacement map,
  distance, Palette, or best fit.
- Issue #33 owns the explicit mapping acceptance matrix.

## Consequences

- SPA preserves all documented native mapping choices without confusing an explicit
  `default` with missing input.
- Agents receive stable string enums and resolved result facts even when Aseprite's
  implementation name is more specific than its requested `default` token.
- Unknown-value fallback remains blocked at the public boundary.

## Rejected alternatives

### Reject every `default` token

This removes deterministic native behavior, including Color Best Fit Criteria's
distinct Default choice, and is an unnecessary restriction of Aseprite capability.

### Treat omission as `default`

`ChangePixelFormat` reads editor preferences when the parameter is not set, so the
two requests are not behaviorally equivalent.

### Normalize the native strings into new enum names

Renaming `linearizedRGB`, `ciexyz`, or `cielab` adds a translation vocabulary without
adding capability. The public strings already form a documented Aseprite contract.

### Accept unknown values because Aseprite falls back safely

The fallback hides caller errors and makes a typo indistinguishable from an explicit
native choice.
