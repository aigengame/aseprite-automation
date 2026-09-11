# ADR-0019: Preserve linked-Cel sharing during raster mutation

- Status: Accepted
- Date: 2026-09-10

## Context

Aseprite linked Cels share native Cel data, including their Image. Editing that shared
Image changes every Cel in the linked set. Aseprite provides unlinking as a distinct
operation that copies the data and Image for one Cel.

An agent can select a Cel without realizing that its Image is shared. SPA therefore
needs observable impact information. It must also avoid applying the same raster action
more than once when a multi-Cel selection contains two links to the same Image.

SPA could implicitly unlink, reject linked targets, or add a generic link-policy
parameter to every raster command. Each would replace a native Aseprite behavior with a
SPA policy and would make equivalent commands diverge over time.

## Decision

Image and Paint Operations preserve Aseprite's native linked-Cel sharing.

- Target resolution identifies the underlying shared Images and applies the requested
  raster mutation once per unique Image.
- The Operation Result reports every Cel affected through the mutated shared Images
  with its domain-specific Layer and Frame facts, including affected Cels outside the
  caller's original target set.
- Relevant read Operations expose enough link-set facts for an agent to predict that
  impact before mutation.
- SPA never implicitly unlinks a Cel and does not add a generic `link_policy` parameter
  to raster Operations.
- An agent that needs an isolated edit explicitly executes `cel unlink` before the
  Image or Paint Operation. Both steps can run in one Operation Plan.

The Lua Operation Kernel owns unique-Image resolution and mutation semantics. Python
adapters and Plan execution do not reconstruct the linked set or implement a second
version of this behavior.

## Consequences

- SPA behavior matches the native Aseprite model instead of silently changing links.
- Agents receive complete impact information rather than mistaking one selected Cel for
  the full mutation scope.
- Multi-selection cannot accidentally apply a paint action repeatedly to one shared
  Image.
- Isolated editing remains fully supported through an explicit, composable native
  operation.
