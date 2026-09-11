---
status: accepted
---

# Model command navigation separately from module ownership

Command Groups organize the public CLI and schema surface for discovery. Domain
Modules organize cohesive behavior and change. They are not required to map one to one.

A Domain Module is a vertical ownership boundary, not a Domain Layer, Command Group,
bounded context, service, or deployment unit. It owns the feature family's language
and rules, request and result contracts, Operation Descriptors, application use cases,
human rendering, and packaged Lua handler bindings while keeping those logical
responsibilities distinct.

Logical source dependencies remain directed even when a slice is physically grouped:

- inbound adapters invoke Descriptor-projected Application entry points;
- Application coordinates domain rules and inner-owned ports;
- Domain rules do not depend on access channels, process execution, filesystems, or
  concrete adapters;
- outbound adapters implement inner-owned ports; and
- the composition root binds concrete adapters, modules, and entry points.

An Operation Descriptor belongs to its Domain Module at the application-contract
boundary. The Lua Operation Kernel owns Core Operation Semantics, while the Aseprite
adapter owns shared protocol and process mechanics. Cross-module use cases coordinate
through Application contracts; modules do not form cyclic dependencies or coordinate
through shared mutable state.

Inspection and Validation stay with the concepts they observe instead of becoming
horizontal subsystems. Physical packages and further module splits follow demonstrated
change clusters; the command tree and filesystem layout do not become parallel
registries.
