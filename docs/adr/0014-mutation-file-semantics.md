---
status: accepted
---

# Require explicit source, target, and in-place mutation intent

Mutation Operations distinguish a Source Sprite File from a Target Sprite File. Creating a Sprite has no Source and requires a Target. Editing an existing Sprite requires a Source and exactly one output intent: a distinct Target, or explicit `in_place` intent that makes the Source path the Target path.

SPA does not infer a Target filename. After path normalization, Source and Target equality without `in_place` is rejected rather than interpreted as an overwrite. When `in_place` is selected, a separate Target argument is rejected so one request cannot express conflicting intent.

An ordinary Mutation Operation resolves and validates its complete target set before changing it. It has no skipped-target success branch or generic best-effort mode. If any selected target cannot satisfy the Operation contract, the Operation fails and performs no Target Commit.

The Lua Operation Kernel saves to a Staged Sprite File created as a sibling of the Target. SPA performs a Target Commit only after the Kernel Response, declared Postconditions, and staged `.aseprite` file have been validated. A failed Operation or Operation Plan does not replace the Target. A retained staging file is either cleaned up or explicitly identified as diagnostic material; it is never reported as a committed Target.

This is single-mutation correctness, not a general consistency facility. SPA does not add expected-digest preconditions, caller locks, write coordination, or multi-writer guarantees. The local caller owns coordination outside the invocation.

Read Operations have no Target. Export Operations use their own declared Artifact outputs and do not overload Source/Target mutation terminology. An Operation Plan remains limited to at most one Target Sprite File as decided by ADR-0003.
