# ADR-0020: Make ordinary mutations all-or-nothing over their target set

- Status: Accepted
- Date: 2026-09-10

## Context

Many SPA Operations can address more than one Layer, Frame, Cel, Image, Tile, or other
native object through their operation-specific target fields. A mutation could discover
after changing some targets that another target is missing, locked, of the wrong type,
outside a Domain Bound, or otherwise unsupported.

Returning success while recording skipped targets as warnings would force agents to
reverse-engineer whether the requested state was actually achieved. A generic
`best_effort` or `continue_on_error` option would multiply that ambiguity across every
mutation and across Operation Plans.

Aseprite transactions and SPA's staged Target Commit provide the mechanisms needed to
offer a stronger public contract, but the public semantic must be stated independently
from either implementation detail.

## Decision

Every ordinary Mutation Operation is all-or-nothing over its complete resolved target
set.

- Before the Operation changes the Sprite, the Lua Operation Kernel resolves all of
  its target fields, enforces the Operation's target-count rules, expands native
  effects such as linked Cels, and validates every target and applicable Domain Bound.
- If any target cannot satisfy the Operation contract, the Operation fails. It does
  not report a successful subset, hide skipped targets in warnings, or perform a
  Target Commit.
- On success, the Operation Result reports the complete resolved and affected scope
  required by that Operation's typed result.
- SPA provides no generic `best_effort`, `continue_on_error`, or partial-success mode
  for ordinary mutations.
- A future workflow with a proven need for tolerant batch processing must define a
  separate Operation with explicit item-level semantics. It does not weaken existing
  Mutation contracts through a universal switch.

The same rule applies to each Mutation Step and to the overall Operation Plan. Any
failed Step or unmet Postcondition aborts the plan and prevents its Target Commit.

## Consequences

- Agents can treat a successful mutation as proof that its whole requested target set
  was handled.
- Errors remain failures rather than warning-shaped partial state.
- Multi-target handlers must perform a resolve-and-validate pass before their mutation
  pass.
- Aseprite transaction rollback and staged file replacement implement the guarantee at
  different layers without becoming new distributed-consistency infrastructure.
