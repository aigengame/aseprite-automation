# ADR-0022: Follow Aseprite's native Layer UUID persistence

## Status

Accepted

## Context

Agents need to inspect a Layer and address it in a later Operation without silently
choosing another Layer when names are duplicated. Aseprite exposes `Layer.uuid` and
the Sprite-level `useLayerUuids` option. A Layer UUID exists in memory even when the
option is disabled, but Aseprite writes and restores Layer UUIDs only when
`useLayerUuids` is enabled. A UUID observed while persistence is disabled can change
after save, close, and reopen.

Enabling the option is an Aseprite-native document capability, not a separate SPA
identity system. Even so, changing it silently on an existing Sprite would be an
undeclared document mutation and would alter a file merely because it was inspected
or targeted.

## Decision

- `sprite create` enables Aseprite's native `useLayerUuids` option by default and
  exposes an explicit creation option to disable it.
- Operations that open an existing Sprite preserve its current `useLayerUuids`
  value. Inspection and target resolution never enable it implicitly.
- Sprite inspection reports whether `useLayerUuids` is enabled.
- A `layer_uuid` is a Persistent Identity and a valid cross-Operation Layer address
  only when the owning Sprite persists Layer UUIDs.
- A process-generated UUID observed while persistence is disabled is not presented
  or accepted as a persistent cross-Operation address.
- SPA does not introduce a parallel Layer identity when Aseprite's native UUID
  satisfies the functional requirement.

## Consequences

- New SPA-authored Sprites are ready for stable Layer addressing without inventing
  SPA metadata.
- Existing author intent and file settings are preserved unless a caller explicitly
  requests a separate supported change to `useLayerUuids`.
- Layer contracts must still define an exact non-UUID addressing form for Sprites
  whose UUID persistence is disabled.
- Issue #8 owns the Layer identity and addressing acceptance matrix.

## Rejected alternatives

### Always enable Layer UUIDs when opening a Sprite

This makes a read or unrelated mutation change document metadata and hides a side
effect from the caller.

### Treat every `Layer.uuid` value as persistent

This contradicts Aseprite's file behavior when `useLayerUuids` is disabled and would
return addresses that fail in the next process.

### Store an SPA-specific Layer key instead

Aseprite already supplies the required persistent identity. A parallel key would
duplicate native capability and create unnecessary synchronization work.
