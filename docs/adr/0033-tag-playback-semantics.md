# ADR-0033: Preserve the Tag model, addressing, and playback context

## Status

Accepted

This ADR consolidates the durable cross-feature decisions from ADR-0034. Issue
#15 owns the exact Tag feature contract and acceptance.

## Context

Aseprite Tags persist an inclusive Frame Range, Animation Direction, and
`repeats`. A zero repeat value is an unspecified sentinel whose observed
playback depends on the consuming context. Tags have no persisted object ID,
their one-based collection order can change after range edits, and duplicate
names are valid.

SPA must preserve the native stored facts while giving agents deterministic
current-snapshot targeting and explicit playback or export behavior.

## Decision

- Tag schemas preserve the native Animation Directions and integer `repeats`
  from 0 through 65535. Zero remains unspecified and is not normalized to
  infinite.
- A Playback or Export Operation that consumes a Tag declares how it interprets
  the Tag and reports the concrete Frame sequence and output loop facts. Those
  facts do not rewrite the Tag.
- `tag_index` is the one-based position in the current Tag order and is not
  Persistent Identity.
- An existing Tag can be addressed by current index or by a name that matches
  exactly once. Missing and ambiguous names fail instead of selecting the first
  match.
- SPA does not expose a process-local object ID, require unique names, assign a
  synthetic Tag identity, or introduce a universal Selector.
- Structural mutation rereads and returns the resulting Tag and current index.

## Consequences

Inspection round-trips actual Aseprite data. Agents can distinguish stored Tag
metadata from playback and export interpretation, and can refresh
snapshot-relative addresses after structural changes.

## Rejected alternatives

Calling zero repeats “infinite” misdescribes some native consumers. A second
stored loop count creates another authority. First-name matching can mutate the
wrong Tag, while a synthetic UUID adds metadata that Aseprite does not persist.
