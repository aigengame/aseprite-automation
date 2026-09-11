---
status: accepted
---

# Separate the Published Language from the private Kernel Protocol

Operation Descriptors define SPA's Published Language: the public request, result, failure, Operation metadata, Artifact, and Surface Manifest schemas. The Aseprite adapter and Lua Operation Kernel communicate through a separate versioned Kernel Protocol. The protocol is private to the installed SPA implementation and is translated at the adapter boundary rather than exposed as another public contract.

Python validates the public request and resolves omitted values, defaults, and meaningful public null semantics before transport. As part of Application Layer orchestration, it may also encode the accepted use case's private ordering and composition of packaged Kernel capabilities. That structure carries data and fixed handler references, never generated Lua or a second public workflow language; it is derived from one accepted Operation contract or the separately bounded Operation Plan contract rather than arbitrary executable code. Where null must remain distinct across the Lua boundary, the Kernel Protocol uses an explicit tagged representation. The protocol does not assume that decoded JSON null remains a value in Lua.

Kernel handlers may read decoded request objects and arrays, but they do not echo or embed arbitrary decoded userdata into newly assembled Lua tables. Aseprite's JSON decoder returns object and array userdata whose shape can be lost when recomposed, including loss of the empty-object versus empty-array distinction. A handler constructs a new Kernel Response from Aseprite facts and ordinary response values. Python then combines that response with process diagnostics and verified Artifact facts, translates it into the public result or failure model, and validates the Published Language output.

Every Kernel invocation writes an explicit, protocol-versioned success or failure response. Aseprite process exit status is diagnostic evidence, not the Operation verdict: exit zero without a valid success response is a typed protocol failure, and a Kernel failure response remains a failure even when Aseprite exits zero.

The Kernel Protocol serves the data shapes required by delivered Operations. SPA does not create a general serialization framework, and Lua does not maintain public schemas, defaults, CLI names, Artifact reporting, or public failure classification.
