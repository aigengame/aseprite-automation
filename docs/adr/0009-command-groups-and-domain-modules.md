---
status: accepted
---

# Model command navigation separately from module ownership

Command Groups organize the public CLI and schema surface for discovery by agents and humans. They are normally named after Aseprite objects or cohesive Aseprite concepts. Domain Modules organize code ownership and change. SPA does not require a one-to-one mapping between them.

A Domain Module is a vertical cohesion and ownership boundary, not a Domain Layer,
Command Group, Bounded Context, service, or deployment unit. It owns a feature slice's
domain language and rules, public request and result contracts, Operation Descriptors,
application use cases, human rendering, and packaged Lua handler bindings. Those
responsibilities can occupy distinct logical areas inside the same module.

Logical source dependencies remain directed even when a slice is physically grouped:

- CLI and MCP inbound adapters invoke Descriptor-projected Application entry points;
- Application use cases depend on domain rules and inner-owned ports;
- Domain rules do not depend on Typer, MCP, process execution, the filesystem, or a
  concrete outbound adapter;
- Aseprite, file, and Artifact outbound adapters implement inner-owned ports and can
  depend on those contracts, while Application and Domain do not import the concrete
  adapters; and
- the bootstrap or composition root is the only area that binds concrete adapters,
  Domain Modules, and entry points.

An Operation Descriptor belongs to its Domain Module at the application/contract
boundary. It can name a stable packaged Kernel handler binding without importing the
concrete process runner. The bound Lua Kernel handler remains the sole behavior
authority for the Operation's Core Operation Semantics; the Aseprite adapter owns the
shared Kernel Protocol, runtime discovery, resource loading, and process mechanics.
Python Application orchestration may select and compose packaged capabilities but
cannot duplicate their native behavior.

Cross-module use cases are coordinated in the Application Layer through public
contracts. Domain Modules do not form cyclic source dependencies or coordinate through
shared mutable state. The composition root mounts CLI projections from the descriptors.
MCP and aggregate schemas derive from the same authority, so neither filesystem layout
nor a module list becomes another registry.

Most stable Aseprite concepts may naturally align with one Command Group and one Domain Module. Exceptions remain explicit when behavior shares a lifecycle and reason to change. Tilemap and Tileset, for example, retain separate navigation groups while a cohesive tile module may own their creation, sharing, identity, placement, cleanup, and save/reopen semantics. Inspection and Validation stay in the module of the object they observe rather than becoming horizontal subsystems.

This follows gda's vertical-slice principle without copying its eventual one-module-per-command-group layout as an up-front constraint. gda adopted that layout after its central files reached thousands of lines and its command groups had demonstrated independent change clusters. SPA modules can become packages or split further when delivered functional breadth produces equivalent evidence. Step 3 selects the initial module inventory and physical directory names together with feature issue decomposition; this decision fixes only ownership and dependency rules.
