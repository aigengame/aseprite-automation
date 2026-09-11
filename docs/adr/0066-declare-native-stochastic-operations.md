# ADR-0066: Classify deterministic and native-stochastic Operations

## Status

Accepted

## Context

Some Aseprite Operations intentionally use native randomness that its Lua API cannot
seed. Requiring identical pixels from every Operation would remove Aseprite-equivalent
functional capabilities; replacing the generator would create a second semantic
authority.

## Decision

- Every Operation Descriptor declares Operation Determinism, projected through the
  Surface Manifest and Operation Result.
- `deterministic` means that the same validated request, source state, supported
  runtime, and declared environment facts produce the same governed domain result.
  Byte-identical Artifacts require a stronger format-specific declaration.
- `native-stochastic` means that Aseprite intentionally uses native randomness that SPA
  cannot seed. Configurable inputs, target, mutation boundary, and observation remain
  explicit, but exact result replay is not promised.
- Native-stochastic results include their classification and complete actual
  observations applicable to the Operation, such as affected region, changed count,
  content digest, and persisted-result verification.
- Deterministic native-tool gates prove exact native pixels. Native-stochastic gates
  prove native delegation, result bounds and invariants, actual-result observation,
  atomicity, and state restoration.
- SPA does not add a general RNG, public seed, replay log, or stochastic-execution
  subsystem. Operation Determinism is functional contract metadata, not an NFR
  platform.

## Consequences

- Repeatability cannot silently remove a native Aseprite functional capability.
- Agents can distinguish repeatable results from verified but stochastic native
  results before invocation.
- Verification uses exact repeat fixtures where meaningful and native invariants plus
  actual-output evidence for stochastic behavior.

## Rejected alternatives

### Require every Operation to produce identical pixels

That would exclude Aseprite's native stochastic authoring capabilities for an NFR.

### Add a SPA random seed or replacement distribution

Aseprite exposes no matching seed contract, so SPA would create a second operation
semantic.

## Consolidates

This ADR retains the cross-feature Operation Determinism decision previously mixed with
the Spray feature contract and repeated by ADR-0067, ADR-0069, and ADR-0073. Issue #29
owns Spray and Jumble contracts and Capability Gaps; issue #28 owns deterministic
Gradient, Contour, and Blur delivery evidence.
