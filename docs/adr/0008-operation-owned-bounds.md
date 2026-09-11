---
status: accepted
---

# Keep bounds with operations instead of building resource governance

Each functional area owns the bounds and units that make its Operations meaningful and usable. Paint owns raster payload geometry and representation constraints. Tilemap inspection owns region or chunk selection and can expose an explicit Artifact projection when cell data is unsuitable for a structured inline result. It reports exact Inspection Coverage and never silently truncates. Operation Plan owns its composition boundary, including Plan Step count. Other Operations introduce bounds when their functional contract requires them.

The Aseprite adapter retains direct Execution Guards for one process invocation, including timeout and captured-output limits. These guards protect the ability to complete and observe the Operation; they do not form a caller-facing quota language, a shared multidimensional budget ledger, or a resource-governance subsystem.

The second prototype demonstrated that tile-bitmap pixels and tile cells are different units and that a full tilemap observation can become unusable. The architectural conclusion is domain ownership of those units and an appropriate result shape, not mandatory registration of every possible resource dimension on every Operation Descriptor.

An inspection that exceeds its declared Domain Bound returns a typed failure with the
applicable allowed range unless the caller selected a supported domain-specific
window, chunk, page, or Artifact projection. Bounds do not authorize partial success.

SPA therefore does not require a universal list of request bytes, operation count, raster pixels, tile-bitmap pixels, tile cells, tiles, frames, cels, runtime, diagnostics, response bytes, and artifact limits across the whole surface. It does not aggregate those dimensions into a central budget policy. Operation tests exercise their own Domain Bounds; adapter tests exercise process timeout and diagnostic capture behavior.
