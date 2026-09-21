---
status: accepted
---

# Publish distinct Operation outcomes and verified Artifacts

This decision consolidates ADR-0015.

Every Operation publishes one success schema and participates in one public failure
channel. A successful CLI invocation exits zero and emits a schema-valid Operation
Result in JSON mode. A failed invocation exits non-zero and emits a schema-valid
Failure Envelope. Success models do not contain failure branches, and failures are not
encoded as nominal success.

Failure Envelopes contain a stable Failure Code, a well-defined Failure Category, and
a human message. Typed code-specific details and diagnostics are present when they
affect recovery. Agents branch on the code; categories support cross-code policy;
messages and diagnostics are explanatory rather than stable parsing surfaces. Human
output is rendered from the same models, and MCP relays the same outcome taxonomy.

The Published Language failure contract uses one shared machine-readable registration
for public Failure Code semantics. A registered code has one stable meaning, Failure
Category, and applicable Failure Details kind. Published codes use
`lower_snake_case`; their meaning and classification are not silently repurposed.
`input` denotes an invalid request; `environment` denotes an unavailable Aseprite
runtime, an incompatible observed runtime, or a missing required resource;
`execution` denotes failure to carry out an accepted
Operation; and `kernel_protocol` denotes a missing or invalid private Kernel Protocol
response after Aseprite exits successfully. It does not classify arbitrary protocol
errors, Aseprite process failures, or Kernel handler refusals.
Private adapter issue kinds and Kernel transport facts are not public Failure Codes.
The initial runtime compatibility contract publishes `runtime_incompatible` with the
observed Lua and API versions, their declared requirements, and the capabilities
required by the selected Descriptor but absent from the runtime observation. A caller
can distinguish that unsupported runtime before Operation execution. The probe's
scripting, file I/O, and JSON transport are fixed prerequisites of producing those
observations; their failure remains on the applicable typed process or Kernel failure
channel.

The shared registration defines code semantics, not another Operation registry. Each
Operation Descriptor declares its applicable registered codes and projects a failure
schema that enumerates those codes and binds each to its Category and Details kind.
SPA validates the same association when constructing a Failure Envelope; an
unregistered code or mismatched association cannot be published as a valid outcome.
Before a CLI Operation Descriptor can be selected, the Access Projection constructs
usage failures such as an unknown command from that same registration, without
inventing a Descriptor. Aggregate `spa schema` discovery separately publishes an
Access-level failure schema for these applicable registered codes and their
Category/Details associations; per-Operation schemas remain Descriptor projections.
The Application classifies private runtime evidence; packaged Lua handlers remain
authoritative for native Core Operation failure conditions, which the Application
validates and translates at the public boundary without reimplementing them. For a
selected Operation, Access adapters project the resulting envelope rather than
inventing another taxonomy.

A feature adds a public code only when callers need a distinct stable decision from
existing codes. The feature's planned contract names the code and required recovery
facts; its implementation adds the registration, applicable Descriptor or Access-level
declaration, producer or classifier, and tests that accept declared combinations and
reject unregistered or mismatched code/Category/Details combinations together. A
planned but unimplemented code is not advertised in an installed failure schema. CLI
process exit policy is an Access projection rather than a property repeated per code:
the initial CLI contract uses exit 2 for `input` and 1 for other structured failures.

Inspection and Validation Results report the native facts appropriate to their domain.
SPA does not impose a common Observation base model. Inspection completeness and bounds
follow ADR-0008. A completed Validation can return Findings as success; an execution
failure or unmet Plan Postcondition returns a Failure Envelope.

An Artifact is a file produced and verified by an Operation. Its common public facts
are path, role, format, byte size, and SHA-256 digest. Format-specific facts remain in
the owning Operation Result. SPA does not add an Artifact Record layer, persistent
manifest, catalog, provenance graph, or audit history. The installed Surface Manifest
describes callable Operations and is not an output Artifact manifest.
