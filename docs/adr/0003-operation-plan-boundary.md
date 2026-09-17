---
status: accepted
---

# Define Operation Plan, validation, and guard semantics

This decision consolidates ADR-0004 and ADR-0005.

An Operation Plan composes Sprite-bound read and mutation Operations against one
in-memory Sprite. A read-only plan commits nothing; a mutating plan commits at most one
declared Sprite target. Only Operations whose Descriptors declare Plan eligibility can
be Steps. Export and `script run` are not eligible. Cross-Sprite workflow, retry, and
partial success remain outside the Plan boundary.

Validation is a read purpose, not an Execution Kind or horizontal subsystem. A
completed Validation reports typed Findings when inspected content does not conform to
a rule. Request invalidity, execution failure, and an unmet commit gate remain failures
rather than Findings.

Plan guards have three phases:

1. Preflight checks schemas, known Operations, admitted Step kinds, paths, and other
   statically decidable rules before Aseprite starts.
2. A Step Precondition resolves document-dependent targets and checks the complete
   target set immediately before that Step mutates the current Sprite.
3. A Postcondition evaluates the state required for Step or Plan success and commit.

Failure in any phase aborts the Plan and prevents Target Commit. A document-dependent
target may refer to an object created by an earlier Step, so SPA does not claim that all
targets resolve before process launch. The enforceable guarantee is that each mutation
resolves and validates its complete target set before it begins.

The Plan is one adapter unit of work rather than a distributed transaction. Aseprite
transactions protect supported in-memory document mutations, while staged replacement
protects the declared file target. Multi-Sprite workflow, exports, retries, and output
aggregation remain caller or Asset Pipeline responsibilities.
