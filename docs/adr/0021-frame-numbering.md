# ADR-0021: Define the public Frame model

## Status

Accepted

This ADR consolidates the durable cross-feature decisions from ADR-0031 and
ADR-0032. Issue #11 owns the exact feature contract and acceptance.

## Context

Aseprite's editor and Lua API expose one-based Frames, while some native CLI
options and internal storage use zero-based positions. Lua exposes Frame
duration as floating-point seconds, but the Sprite model and file format store
integer milliseconds. Aseprite also distinguishes adding an empty Frame from
duplicating a Frame and its Cels.

SPA needs one public model that agents can copy between Frame, Cel, Tag,
animation, validation, Plan, and export Operations without transport-specific
conversion or hidden editor policy.

## Decision

- The public address is **Frame Number**, encoded as one-based
  `frame_number`. An unqualified `index` is not a Frame address.
- A public Frame Range contains inclusive Frame Number endpoints.
- Persisted Frame timing is `duration_ms`, an integer from 1 through 65535.
  Seconds and zero-based positions remain private adapter or Kernel details.
- FPS can be an operation-specific convenience input only when its deterministic
  conversion reports the resulting `duration_ms` values. FPS is not another
  stored timing authority.
- Empty Frame addition and Frame duplication remain distinct Operations.
  Duplication makes Cel copy or link intent explicit instead of deriving it
  from Layer or editor state.
- Internal conversions are performed by the adapter or Lua Operation Kernel.
  Public requests, results, diagnostics, and schemas use the same model.

## Consequences

Agents can reuse inspected Frame facts without translation. SPA preserves the
actual timing resolution and distinguishes an empty timeline position from
copied animation content. Export-specific timing remains an output fact and
does not rewrite Sprite timing.

## Rejected alternatives

Zero-based public indexes conflict with Aseprite's editor and Lua language.
Publishing both seconds and milliseconds creates two representations of one
persisted fact. A single ambiguous “new frame” operation hides whether content
and links are inherited.
