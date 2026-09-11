# ADR-0034: Address Tags by current index or unique name

## Status

Accepted

## Context

Aseprite exposes `Sprite.tags` to Lua as a one-based array. It sorts Tags by their
Frame Ranges, and changing a Tag range removes and reinserts the Tag, so its array
position can change. Aseprite does not enforce unique Tag names; native name lookup
returns the first match.

Every in-memory Tag has an internal Aseprite object ID, but the Lua Tag API does not
expose it and the `.aseprite` Tags chunk does not persist it. It therefore cannot
identify a Tag across separate SPA invocations or a save, close, and reopen cycle.
Adding a synthetic UUID would create metadata and lifecycle rules that Aseprite does
not need to provide the accepted Tag editing capability.

Agents still need exact, inspectable target semantics. Silently selecting the first
duplicate name is unsuitable for deterministic mutation, while a universal Selector
would generalize a problem that has a small Tag-specific solution.

## Decision

- `tag_index` is the public one-based position in the current `Sprite.tags` order.
  It is a current-snapshot address, not a Persistent Identity.
- A Tag read or mutation request accepts exactly one of `tag_index` or `tag_name`.
  Operations that do not target an existing Tag, such as `tag list` and `tag add`,
  do not accept either field.
- `tag_name` resolution searches the complete Tag collection. Zero matches fail as
  not found; more than one match fails as ambiguous. SPA never adopts Aseprite's
  first-match behavior for a mutation.
- Aseprite-compatible duplicate Tag names remain valid. SPA does not impose global
  name uniqueness merely to simplify addressing.
- Tag inspection returns the current index and complete persisted Tag facts. A
  successful mutation rereads and returns the resulting Tag and its current index,
  including after range-driven reordering.
- SPA does not expose the native process-local object ID, assign a Tag UUID, or use
  an SPA Key as a default Tag identity.
- Tag resolution is implemented by the Lua Operation Kernel as part of each Tag
  Operation's semantics; it does not introduce a cross-domain Selector or Locator.

## Consequences

- Agents can inspect and mutate duplicate-named Tags without hidden first-match
  behavior.
- Callers treat an earlier index as snapshot-relative and use the resulting facts or
  fresh inspection after structural Tag changes.
- The public model stays aligned with Aseprite's actual persisted data and collection
  semantics.
- Tests cover one-based bounds, unique and duplicate names, ambiguity, range-driven
  reordering, result rereads, and save/reopen behavior.

## Rejected alternatives

### Expose Aseprite's internal Tag object ID

It is not available through the Lua API and is not persisted in the `.aseprite` Tags
chunk, so it cannot satisfy cross-invocation identity.

### Persist a synthetic Tag UUID or SPA Key

No accepted Tag workflow requires persistent identity beyond current index and
unique-name addressing. The extra metadata contract would not be proportional.

### Require globally unique Tag names

Aseprite permits duplicates. Enforcing uniqueness would reduce its business
capability and reject otherwise valid documents.

### Select the first matching name

That mirrors one native helper but makes a destructive operation depend on hidden
collection order.

### Introduce a universal Selector

Tag addressing does not justify a cross-domain query language or target hierarchy.
