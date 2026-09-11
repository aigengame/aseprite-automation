# ADR-0033: Preserve Tag playback fields and make consumption explicit

## Status

Accepted

## Context

Aseprite Tags persist an inclusive Frame Range, an Animation Direction, and an
integer repeat value. The native directions are Forward, Reverse, Ping-pong, and
Ping-pong Reverse. `Tag.repeats` is stored from 0 through 65535, but zero is an
unspecified sentinel rather than one universal playback count: Aseprite's editor can
loop it indefinitely while export or play-once traversal uses a finite interpretation.
Ping-pong traversal also gives zero and one observably different behavior.

Calling zero “infinite” in SPA would lose the persisted native fact and misdescribe
an export. Conversely, introducing another loop-count property on Tag would create a
second authority not stored by Aseprite.

## Decision

- Public Tag schemas use `animation_direction` with `forward`, `reverse`,
  `ping-pong`, or `ping-pong-reverse`.
- Public Tag schemas preserve the native field concept `repeats` as an integer from
  0 through 65535. Zero is documented and reported as unspecified, never normalized
  to infinite.
- `tag add` requires an explicit inclusive Frame Range, Animation Direction, and
  `repeats`; it does not inherit editor defaults.
- Tag inspection reports the raw persisted fields and does not add a second stored
  `loop_count`.
- Every Playback or Export Operation that consumes a Tag declares its Playback
  Context: apply Aseprite Tag semantics or use a caller-declared play count supported
  by that Operation.
- A consuming result reports the exact expanded Frame Number sequence and applicable
  encoded timing and output loop facts, including Ping-pong endpoints and the
  interpretation of zero repeats.
- Export-format loop facts belong to the Export Operation Result and never rewrite
  the Tag.

## Consequences

- Inspection round-trips the actual Aseprite Tag without inventing an interpretation.
- Agents can verify the concrete animation traversal produced for an export.
- Editor playback, play-once traversal, and output-format looping can differ without
  corrupting the persisted Tag model.
- Issue #15 owns Tag playback acceptance.

## Rejected alternatives

### Normalize `repeats = 0` to infinity

That describes editor looping but not Aseprite export or play-once behavior.

### Replace `repeats` with a new loop-count field

This departs from Aseprite's persisted model and still cannot represent all playback
contexts with one number.

### Let each exporter silently interpret Tags

Agents could not predict or verify the Frame sequence or loop behavior from the
request and result contract.
