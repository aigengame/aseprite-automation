---
status: accepted
---

# Make mutations explicit, all-or-nothing, and staged

This decision consolidates ADR-0020.

A Mutation Operation distinguishes its Source Sprite File from its Target Sprite File.
Creation has no Source and requires a Target. Editing requires a Source and either a
distinct Target or explicit in-place intent. SPA does not infer an output name or
interpret source-target equality as implicit overwrite.

Every ordinary Mutation is all-or-nothing over its complete resolved target set. Before
changing the Sprite, the Lua Operation Kernel resolves target fields, enforces target
count, expands native effects such as linked Cels, and validates every target and
applicable Operation Limit. Failure does not produce a successful subset or Target Commit.
SPA has no generic best-effort, continue-on-error, or partial-success switch.

Supported in-memory document changes run within the declared Aseprite transaction. The
Kernel saves to a staged Sprite file beside the Target; SPA replaces the Target only
after validating the Kernel response, Postconditions, and staged file. Staging material
is never reported as a committed Target.

The Application coordinates this validation. Before the one Aseprite invocation
returns, packaged handlers close, reopen, and inspect the staged Sprite when an
Operation requires persisted native facts. The Aseprite adapter owns process and
protocol mechanics. The File Adapter validates domain-neutral file facts and performs
the Target Commit; it does not interpret Aseprite document semantics.

The same failure and commit rule applies to a Mutation Step and its Operation Plan.
This is single-invocation mutation correctness, not multi-writer coordination or a
general consistency facility. The caller owns external locking and workflow. Read
Operations have no Target, while Export Operations publish their own declared Artifact
destinations.
