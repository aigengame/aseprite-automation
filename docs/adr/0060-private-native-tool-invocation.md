# ADR-0060: Drive Paint primitives through a private Native Tool Invocation

## Status

Accepted; deterministic-delivery clause amended by ADR-0066

## Context

Aseprite exposes `Image.context`/`GraphicsContext` and `app.useTool`. GraphicsContext
uses a graphics-path abstraction and does not define the same pixel behavior as the
editor's Pencil, Line, Rectangle, Ellipse, and Fill tools. `app.useTool` invokes those
native tools, but omitted options fall back to active editor state and preferences.

SPA needs editor-equivalent Paint behavior with explicit agent inputs. The required
state control serves that functional outcome and must not grow into general session
or coordination infrastructure.

## Decision

- Native Tool Invocation is a private mechanism owned by the fixed Lua Kernel.
- Each public Paint primitive retains its own typed Operation Descriptor, fixes the
  corresponding native tool, and exposes the parameters relevant to that intent.
- SPA does not expose a generic public `use-tool` command.
- The Kernel passes the explicit Cel, Layer, and Frame and every result-affecting
  option owned by the operation, including applicable colors, Brush, Ink, opacity,
  tolerance, contiguous, Selection mode, Tilemap mode, and Tileset mode.
- Active tool, foreground/background colors, active Brush, active site, and mutable
  tool preferences cannot supply omitted public semantics.
- Primitive geometry is expressed in Image Pixel space. The Kernel translates Points
  and Rectangles through the addressed Cel position into native Canvas coordinates.
- Paint's default bounds refusal, explicit clipping, and explicit Selection
  Application govern primitive execution. The observed changed region is validated
  before Target Commit.
- Native invocation cannot implicitly create a Cel, expand its Image, move it, or
  break Image sharing. Those intents compose `cel add`, `image canvas-resize`, or
  `cel unlink` explicitly.
- Existing ordinary Image and Background Cels are supported, subject to the native
  opaque Background postcondition. Reference, Tilemap, absent, and non-Cel targets
  use distinct operations or fail.
- Linked Images preserve sharing and results report every affected Cel.
- The Kernel captures and restores the editor/tool state it changes for the invocation
  on success and failure. This is invocation-local functional isolation, not a
  persistent session, lock, concurrency, or generalized state-management subsystem.
- GraphicsContext may be used for internal diagnostics or non-authoritative previews;
  it cannot replace the public primitive's native tool semantics.
- Each primitive is delivered after a real `aseprite --script` vertical slice proves
  non-interactive execution, complete configurable option control, independence from
  perturbed editor preferences, declared Operation Determinism, native-tool
  delegation, Linked Image behavior, standalone/Plan atomicity, and state restoration.
  Deterministic operations prove exact pixel parity; native-stochastic operations
  prove native invariants and complete actual-result observation under ADR-0066.
- A failed proof yields that primitive's typed Capability Gap. SPA does not silently
  switch to GraphicsContext or implement a replacement rasterizer in Python.

## Consequences

- Public Paint commands preserve Aseprite editor vocabulary and pixel behavior.
- Agents receive typed operations rather than a stateful editor escape hatch.
- Image geometry and linked relationships do not change as hidden drawing side
  effects.
- State isolation remains bounded to what native tool delegation functionally needs.

## Rejected alternatives

### Make `app.useTool` a generic public command

That would expose editor state and bypass operation-specific schemas and results.

### Use GraphicsContext as the primitive authority

Its path renderer is not the Aseprite pixel-tool semantic agents requested.

### Allow native automatic Cel creation or expansion

It would conflate Paint with Cel and Image lifecycle operations.

### Reimplement editor tools in Python

That violates the Lua Kernel authority and creates a second raster engine.
