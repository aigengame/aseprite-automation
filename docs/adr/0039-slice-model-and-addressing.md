# ADR-0039: Preserve the Slice model and snapshot-relative addressing

## Status

Accepted

Issue #40 owns the exact feature contract, runtime-specific Capability Gap,
and acceptance.

## Context

Aseprite models a Slice as a named Sprite object with ordered Frame-varying
Slice Keys. Each Key contains bounds and optional center and pivot data. The
file format persists no Slice identity, the current collection order can
change, and duplicate names are valid.

Flattening a Slice to one Rectangle would lose animation metadata used by UI,
export, and engine workflows. SPA still needs deterministic targeting without
creating a parallel identity system.

## Decision

- A Slice preserves its name, user data, and complete ordered collection of
  explicit Slice Keys.
- Each Key uses public one-based `frame_number`. Bounds are in Canvas Pixel
  space; center and pivot use Aseprite's native relation to the bounds.
- A Key is effective from its Frame through the Frame before the next Key, or
  through the Sprite's last Frame. SPA creates no synthetic value before the
  first explicit Key.
- `slice_index` is a one-based current-snapshot address, not Persistent
  Identity. A Slice name must match exactly once.
- Structural mutation rereads and returns the resulting current address facts.
- SPA exposes no process-local ID, synthetic UUID, SPA Key, universal Selector,
  or first-name-match mutation.
- Runtime-specific read and mutation reachability is a Capability Gap concern;
  it does not change the persisted Slice model.

## Consequences

Inspection and export can preserve multi-Key animation metadata. Duplicate
names remain valid while mutations stay deterministic, and callers refresh
current indexes after structural changes.

## Rejected alternatives

A static Rectangle loses native timeline semantics. An internal ID or
synthetic UUID cannot provide Aseprite-owned persistence. First-name matching
depends on hidden collection order.
