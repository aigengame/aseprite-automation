# ADR-0035: Model Palettes as Frame-based change points

## Status

Accepted

## Context

Aseprite stores `Sprite.palettes` as an ordered collection of Palettes associated
with Frames. `Sprite:palette(frame)` resolves the latest Palette whose frame is at
or before the requested Frame. That Palette remains effective until a later change.
Most Sprites contain one Palette beginning at the first Frame, while imported image
sequences and supported formats can contain later Palette Changes.

Treating the collection as independent per-Frame Palette copies would misstate the
native model. It would also hide the scope of entry mutation: editing the Effective
Palette observed at one Frame can change the colors used by several Frames.

Palette objects have process-local Aseprite object IDs, but the scripting contract
does not expose those IDs and the `.aseprite` Palette chunk does not persist them.
The Palette collection's current array position is unnecessary because its starting
Frame is the native change-point fact. A Palette Index already means a zero-based
entry within a Palette and must not be overloaded as Palette identity.

## Decision

- A **Palette Change** is a Palette stored at a one-based
  `palette_frame_number`. Changes are ordered by that Frame Number.
- The **Effective Palette** for `frame_number` is the latest Palette Change at or
  before that Frame. Its inclusive effective Frame Range ends immediately before
  the next Palette Change, or at the Sprite's last Frame.
- `palette list` returns all Palette Changes, their starting Frame Numbers, and their
  effective Frame Ranges.
- `palette get` accepts any valid `frame_number`, resolves its Effective Palette, and
  returns the originating `palette_frame_number`, effective Frame Range, and entries.
- Entry mutation, resize, and import target an existing Palette Change by exact
  `palette_frame_number`. Their results report the complete resulting Palette Change
  and affected effective Frame Range.
- Palette Change creation and deletion are not published Operations for Aseprite
  1.3.18.5 because its public Lua/editor surface cannot perform that lifecycle.
  ADR-0038 records this evidence and the conditions for reopening the capability.
- Entry mutation never simulates Palette Change creation when the requested
  `palette_frame_number` does not exist.
- A Palette entry continues to use its native zero-based Palette Index.
- SPA does not use Palette collection position, internal object ID, UUID, SPA Key,
  active editor Palette, or a universal Selector to identify a Palette.

## Consequences

- Agents can distinguish the Palette requested at a Frame from the native change
  point that supplies it.
- A mutation cannot conceal that several Frames share the affected Palette.
- Common single-Palette Sprites use `palette_frame_number: 1` without a special case.
- Frame insertion and removal can move Palette Change Frame Numbers; relevant Frame
  Operations report those native structural adjustments with their other results.
- Tests cover change ordering, effective-range resolution, exact mutation targeting,
  result rereads, save/reopen behavior, and the reported lifecycle Capability Gap.

## Rejected alternatives

### Model one independent Palette per Frame

This duplicates shared native state and makes mutations appear narrower than they
are.

### Mutate the Effective Palette from any Frame without reporting its change point

The request would conceal which Palette is edited and the result could affect Frames
before and after the requested Frame.

### Address Palettes by collection position or object ID

Collection position adds no domain meaning, while the internal object ID is neither
public scripting data nor persisted file identity.

### Create a persistent Palette UUID

The starting Frame provides the required native address. A synthetic identity would
add metadata lifecycle rules without enabling the accepted Palette workflows.

### Let entry mutation create a missing Palette Change

It conflates lifecycle with content editing and makes the affected Frame Range depend
on hidden fallback behavior.
