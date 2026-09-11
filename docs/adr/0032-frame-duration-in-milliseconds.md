# ADR-0032: Publish Frame Duration in integer milliseconds

## Status

Accepted

## Context

Aseprite's Lua `Frame.duration` property uses floating-point seconds, but the native
Sprite model and `.aseprite` Frame header store integer milliseconds. The model clamps
Frame duration to the inclusive range from 1 through 65535 milliseconds. The Lua
setter multiplies seconds by 1000 and converts the result to an integer, so exposing
both representations would create truncation and equality ambiguity at the public
boundary.

Some higher-level animation workflows naturally begin with frames per second, and
some export formats have timing precision different from `.aseprite`. Neither should
replace the persisted Sprite timing fact.

## Decision

- The Published Language names a Frame's persisted timing `duration_ms`.
- `duration_ms` is an integer from 1 through 65535, inclusive.
- Frame inspection, addition, duplication, retiming, validation, Postconditions, and
  Operation Results use that field and unit.
- The Lua Operation Kernel converts milliseconds to the seconds required by the Lua
  API, then rereads and verifies the actual persisted integer milliseconds.
- Core Frame contracts do not also accept `duration_seconds` or an unqualified
  `duration` field.
- A higher-level Animation Operation can accept an FPS convenience input only with a
  declared deterministic conversion and rounding rule. Its result reports every
  actual `duration_ms` value produced; FPS is not stored as another authority.
- When an export format quantizes timing differently, the export Operation Result
  reports the encoded timing separately and does not alter the Sprite's Frame
  Duration facts.

## Consequences

- Public requests map exactly to Aseprite's persisted timing resolution and range.
- Equality and Postcondition checks do not depend on floating-point seconds.
- Agents can still use FPS-oriented workflows while observing the exact timeline
  that was created.
- Export verification can distinguish source timing from encoded output timing.
- Issue #11 owns Frame-duration acceptance; export issues own format quantization.

## Rejected alternatives

### Publish floating-point seconds

This mirrors the Lua accessor but not the stored representation, and it introduces
conversion and precision ambiguity.

### Accept both milliseconds and seconds on every Frame Operation

Two public representations of the same persisted fact complicate validation,
equality, help, and agent-generated requests without adding capability.

### Store FPS as the Frame timing authority

Aseprite stores per-Frame durations, and nonuniform animation timing cannot be
represented by one FPS value.
