# ADR-0066: Declare deterministic and native-stochastic operations

## Status

Accepted

## Context

SPA originally required every Native Tool Invocation slice to prove deterministic
pixels. Aseprite's Spray tool intentionally distributes Brush marks with C `rand()`
and seeds that generator from process time. Aseprite 1.3.18.5 exposes no seed through
its Lua API. Excluding Spray to preserve a universal determinism quality would
contradict SPA's Aseprite-equivalent functional scope; replacing the generator would
contradict native semantic authority.

The same runtime exposes Spray Width `1..32` and Spray Speed `1..100` in the editor,
but not as `app.useTool` arguments. Its headless path resets a Tool's preferences on
first scripted use and then marks that Tool as reset for the process. This suggests,
but does not yet prove, a fixed-Kernel native priming route.

## Decision

- Every Operation Descriptor declares Operation Determinism, projected through the
  Surface Manifest and Operation Result.
- `deterministic` means that the same validated request, source state, supported
  runtime, and declared environment facts produce the same governed domain result.
  Byte-identical Artifacts require a stronger format-specific declaration.
- `native-stochastic` means that Aseprite intentionally uses native randomness which
  SPA cannot seed. Configurable inputs, target, mutation boundary, and observation
  remain explicit, but exact result replay is not promised.
- Native-stochastic results include their class and complete actual observations,
  including affected region, changed count, content digest, and persisted-result
  verification applicable to the Operation.
- Native Tool Invocation gates prove exact native pixels for deterministic operations.
  Native-stochastic gates instead prove native delegation, result bounds and
  invariants, actual-result observation, atomicity, and state restoration.
- SPA does not add a general RNG, public seed, replay log, or stochastic-execution
  subsystem. Operation Determinism is functional contract metadata, not a new NFR
  platform.
- Intended `spa paint spray` invokes Aseprite's fixed `spray` tool over one non-empty
  ordered Image Pixel `points` gesture. It requires Standard Paint Brush, compatible
  Color Value, integer opacity in `0..255`, an accepted Ink, Spray Width in `1..32`,
  and Spray Speed in `1..100`.
- Paint Spray rejects Freehand Algorithm because Aseprite's Spray uses its native
  overlap trace and random Brush placement rather than the Pencil intertwiner chosen
  by that option.
- Paint Spray declares `native-stochastic`. It exposes no seed and returns the actual
  coverage, changed count, pixels/digest, and persisted observations.
- A real `aseprite --script` slice must test whether the fixed Lua Kernel can prime
  native Spray once on an isolated temporary Sprite, then set requested native Width
  and Speed preferences and invoke the real target without persistent temporary state.
- Until that priming route, preference restoration, bounds, Selection, Linked Image,
  atomicity, and actual-result evidence pass, the Surface Manifest omits Paint Spray
  and `spa info` reports an Aseprite-version-specific Capability Gap.
- SPA does not ship a fixed-default-only Spray subset and does not reproduce Spray in
  Python or alternate Lua code.

## Consequences

- A quality preference for repeatability cannot silently remove a native Aseprite
  functional capability.
- Agents can distinguish repeatable results from verified but stochastic native
  results before invocation.
- CI uses exact repeat fixtures where meaningful and invariant plus actual-output
  verification for native-stochastic behavior.
- Spray retains its complete intended contract while exact runtime support remains
  evidence-gated.

## Rejected alternatives

### Require every operation to produce identical pixels

That would exclude Aseprite's native stochastic authoring capabilities for an NFR.

### Add a SPA random seed and distribution

Aseprite exposes no matching seed contract, so SPA would create a second Spray
semantic.

### Ship only native default Width and Speed

It would present a narrow technical accident as the Aseprite Spray capability.

### Claim preference priming works from source inspection alone

The lifecycle, output, restoration, and failure behavior require a real headless
vertical slice.
