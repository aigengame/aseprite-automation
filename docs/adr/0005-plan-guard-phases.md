---
status: accepted
---

# Split plan guards into Preflight, Step Preconditions, and Postconditions

Operation Plan safety uses three guard phases with different evidence and timing.

1. Preflight runs before Aseprite execution starts. It validates request schemas, known Operations, allowed Plan Step kinds, paths, declared Domain Bounds and Execution Guards, and other statically decidable cross-field rules.
2. A Step Precondition runs immediately before its Plan Step against the current in-memory Sprite. It resolves the guarded Operation's target fields, enforces that Operation's target-count rules, validates its complete target set, and checks document-dependent bounds or state. It may refer to an object created by an earlier step.
3. A Postcondition runs after its step or after the plan and asserts the facts required for success and commit.

Failure in any phase is typed. Preflight failure prevents process execution. An unmet Step Precondition prevents its guarded step from mutating the Sprite; if earlier steps mutated it inside the plan's Aseprite transaction, the plan aborts and those changes roll back. An unmet Postcondition likewise aborts the plan. No failed phase permits the declared target to be committed.

The product does not claim that all document targets are resolved before process launch or even before the first mutation. Such a claim is impossible for target fields that depend on an opened Sprite and wrong for steps that address objects created by previous steps. The enforceable promise is narrower and stronger: each Operation resolves its complete target set and enforces its own target-count rules before its mutation begins.

This decision refines the umbrella PRD statement that a plan is validated before process launch. That statement applies to Preflight only; document-dependent selection and assertions belong to their explicit runtime phases.
