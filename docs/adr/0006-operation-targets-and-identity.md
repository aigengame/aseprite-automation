---
status: accepted
---

# Keep target addressing operation-specific and identity evidence-based

Aseprite does not define a universal Selector or cross-object query language. Its
active objects, Range, Selection, collections, indexes, names, references, runtime
IDs, and native UUIDs have different meanings and guarantees.

SPA Operations use explicit targets because agent automation cannot depend on hidden
editor state. Each Operation defines the Aseprite-aligned target fields and target-count
rules required by its behavior. Results report current domain-specific address and
impact facts instead of wrapping every object in a generic locator. Missing or
ambiguous targets fail according to the owning Operation's contract.

Python validates field shapes and statically decidable rules. The Lua Operation Kernel
resolves targets against the live Sprite, expands native effects, enforces target-count
rules, and reports observed facts. A shared target value is extracted after delivered
Operations establish identical semantics; SPA does not start with a universal
Selector, locator hierarchy, query DSL, or cardinality framework.

Persistent identity is evidence-based. Runtime object IDs are not advertised as stable
across save and reopen. A native persistent identity is supported according to its
native lifecycle. When Aseprite has no suitable identity and an accepted functional
requirement needs one, SPA can store a narrowly scoped key in its versioned custom
properties without redefining native identity or creating a universal shadow identity
system.
