---
status: accepted
---

# Limit Operation Plans to one Sprite and one committable source target

An Operation Plan may contain only Sprite-bound read and mutation Operations. Read-only validation and declared postconditions may observe the same in-memory Sprite. Export, script-run, and meta Operations are not valid Plan Steps. A read-only plan commits nothing; a mutating plan commits at most one declared `.aseprite` target.

The plan is one adapter unit of work, not one indivisible transaction. A Sprite is created or opened before an Aseprite `app.transaction` can begin. Each Mutation Step resolves and validates its complete target set before changing it, and supported document mutations then run inside one declared Aseprite transaction. SPA saves to a staged path, validates the structured response and required source artifact, and only then atomically replaces the declared target. A failed or partially applicable step aborts the plan, reports its failed step, and does not commit that target.

This boundary preserves the safety claim proven by the prototypes. Including export would introduce a set of output files that the host filesystem cannot publish as one atomic replacement. Including script-run would also import unrestricted behavior that cannot satisfy ordinary-operation safety guarantees. Excluding both costs additional Aseprite process launches for a create-then-export workflow, but keeps plan failure and commit semantics precise.

Export remains a separate Operation after source commit. Ordering multiple Sprites or exports, retaining successful upstream work, retrying failed stages, aggregating Artifacts, installing files, and accepting them in a project remain responsibilities of the caller or Asset Pipeline.
