---
status: accepted
---

# Keep target addressing operation-specific and identity evidence-based

Aseprite does not define one Selector object or cross-object query language. Its Lua
API exposes active objects, the editor Range, the pixel Selection, object collections,
indexes, names, direct references, runtime object IDs, and a Layer UUID. These
mechanisms have different meanings and guarantees.

SPA Operations need explicit target addressing because a batch agent cannot depend on
hidden editor state. That functional need does not justify a universal Selector,
Resolved Locator, query DSL, or cardinality framework.

Each Operation defines the Aseprite-aligned target fields and target-count rules needed
for its behavior. For example, one command can require one Layer hierarchy path,
another can accept an explicit Frame range, and a search or list command can return
zero or more domain objects. Operation Results report domain-specific native facts such
as Layer hierarchy, Frame number, Cel Layer/Frame coordinates, or affected Cels rather
than wrapping every object in a generic Locator.

Layer Operations use Layer-specific alternatives: a persisted `layer_uuid`, a
`layer_stack_path` composed from one-based native `Layer.stackIndex` values from the
Sprite root, or a convenient `layer_name` that must match exactly once within that
Operation's documented scope. The stack path is an exact address for the current
hierarchy and can distinguish nested or duplicate-named Layers, but reorder or
reparent operations can change it. It is not a Persistent Identity. Missing and
ambiguous Layer targets fail instead of falling back to Aseprite's first name match.
Inspection and structural mutations return the current address facts.

Python validates field shapes and statically decidable cross-field rules. The Lua
Operation Kernel resolves target fields that depend on the current Sprite, rejects
missing or ambiguous targets according to that Operation's contract, expands native
effects, and returns the observed domain facts. A shared value type is extracted only
after delivered Operations prove that its semantics are actually identical; SPA does
not begin with a cross-domain selector hierarchy.

Persistent Identity remains a separate, evidence-based question. A runtime Aseprite
`Object.id` can identify an object inside a live process, but SPA does not advertise it
as stable across save, close, and reopen. An Aseprite-native persistent identity, such
as a Layer UUID when the Sprite uses them, can be supported only with lifecycle
evidence for the pinned runtime.

For Layer UUIDs, SPA follows Aseprite's native persistence switch. A Sprite created
by SPA enables `useLayerUuids` by default unless the create request explicitly opts
out. An existing Sprite retains its current value; inspection and target resolution
never enable the option implicitly. Inspection exposes whether persistence is
enabled, and a UUID generated while it is disabled is not accepted as a persistent
cross-Operation Layer address.

When Aseprite has no suitable persistent identity and an accepted functional
requirement needs one, SPA may store a narrowly scoped SPA Key in its versioned
custom-properties namespace. This exception belongs to that feature rather than a
universal shadow identity system. SPA preserves unrelated custom properties and does
not redefine a native UUID under another name.

Tests for any Persistent Identity include save, close, reopen, and relevant lifecycle
changes rather than inferring stability from one in-memory run.
