# ADR-0066: Classify Operation Determinism

## Status

Accepted

## Context

Some Aseprite Operations intentionally use native randomness that its Lua API cannot
seed. Requiring identical pixels from every Operation would remove Aseprite-equivalent
functional capabilities; replacing the generator would create a second semantic
authority.

The separate `script-run` Execution Kind executes exact caller-owned Lua. Such a script
can depend on time, files, environment state, or randomness that is neither governed nor
classified by SPA.

## Decision

- Every Operation Descriptor declares Operation Determinism, projected through the
  Surface Manifest and Operation Result.
- `caller-defined` is required for `script-run` and prohibited for every other Execution
  Kind. It states that SPA makes no claim about the caller's script repeatability or
  randomness source.
- `deterministic` and `native-stochastic` are required alternatives for `read`,
  `mutation`, and `export`; they are prohibited for `script-run`.
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
- Agents can distinguish both from caller-owned Lua whose behavior SPA does not govern.
- Verification uses exact repeat fixtures where meaningful and native invariants plus
  actual-output evidence for stochastic behavior.

## Rejected alternatives

### Require every Operation to produce identical pixels

That would exclude Aseprite's native stochastic authoring capabilities for an NFR.

### Add a SPA random seed or replacement distribution

Aseprite exposes no matching seed contract, so SPA would create a second operation
semantic.

### Classify caller-owned Lua as deterministic or native-stochastic

Either value can be false for an unrestricted caller script. A dedicated
`caller-defined` value preserves a uniform Descriptor contract without claiming behavior
that SPA does not own.

## Consolidates

This ADR retains the cross-feature Operation Determinism decision previously mixed with
the Spray feature contract and repeated by ADR-0067, ADR-0069, and ADR-0073. Issue #29
owns the planned Spray and Jumble contracts, evidence requirements, and candidate-gap
handling; issue #28 owns the planned deterministic Gradient, Contour, and Blur
contracts and evidence requirements. The issues own provenance links and curated
evidence summaries. Tests and evidence artifacts own executed proof; the installed
Surface Manifest owns installed Capability Gaps.
