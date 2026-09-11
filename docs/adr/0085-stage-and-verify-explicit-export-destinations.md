# ADR-0085: Stage and verify explicit Export Destinations

## Status

Accepted

## Context

Export is a core SPA capability, but Aseprite's non-interactive save seams do not by
themselves provide a reliable completion contract for agents.

In Aseprite 1.3.18.5, the `SaveFileCopyAs` scripting wrapper executes the native
command and then returns `true` without observing its file-operation error. The
Sprite Sheet command checks `askOverwrite` only when UI is available. Its exporter
writes the data file before attempting to save the texture. Consequently, a
headless invocation can overwrite an existing file without a prompt, report a
truthy Lua result and process exit code zero when no requested file was produced,
or leave metadata without its failed texture counterpart.

Issue #7 owns the detailed headless probe evidence and first File Format acceptance.

These are observable export-function semantics. SPA needs enough destination and
completion behavior to make an agent-facing export truthful, but this does not
justify an Artifact registry, backup facility, recovery subsystem, or general
multi-file transaction framework.

## Decision

- Every Export Operation receives one or more explicit Export Destinations. A
  single-file destination declares `path` and an explicit `if_exists` value of
  `fail` or `replace`; no command inherits Aseprite's overwrite prompt, editor
  preference, recent-file state, or an implicit overwrite default.
- A command with a fixed small output set can declare several Destinations directly.
  A generated multi-file export whose cardinality follows domain inputs declares an
  output directory and an Aseprite-aligned Filename Format through its concrete
  command schema. The Operation resolves the complete expected destination set from
  its already bounded Frames, Layers, Tags, Slices, Tiles, or other domain inputs.
  Empty expansions, path collisions, duplicate destinations, unsupported
  placeholders, and an existing destination governed by `fail` are rejected before
  native export.
- The fixed Lua Operation Kernel remains the only authority for selection,
  rendering, encoding, native Filename Format use, and every other core Export
  Operation semantic. Python never creates a temporary Lua operation script or
  implements a substitute exporter.
- The file adapter maps declared final destinations to an operation-owned temporary
  output location and passes those temporary paths to the fixed Kernel handler.
  Path mapping, temporary-directory lifecycle, and file inspection are adapter
  responsibilities rather than alternate export semantics.
- A successful native command, zero process exit, or truthy Lua return is never
  sufficient. Before publishing any Artifact, SPA requires the private Kernel
  Response and every expected temporary file, then validates each file's declared
  format plus the command-specific dimensions, frame/timing, metadata, palette,
  tileset, or other required facts.
- Only validated temporary outputs are published to their declared final paths.
  The Operation returns success only after publication and returns every produced
  file as the existing simple Artifact value. Unexpected native diagnostic output
  remains bounded diagnostics, not a second success protocol.
- This foundation does not promise a filesystem transaction across multiple final
  paths and does not introduce backup, rollback, Artifact Manifest, artifact
  registry, provenance history, or generalized recovery. If a concrete multi-file
  command needs stronger publication behavior, its vertical slice must justify and
  validate that functional requirement without generalizing it to unrelated
  Operations.
- Export staging is distinct from Staged Sprite File and Target Commit. Export
  Operations remain read-only with respect to the Source Sprite and cannot be Plan
  Steps.
- Results report the normalized final destinations, `if_exists` policy, expected
  and produced Artifact roles, format-specific verification facts, and any typed
  failure needed to distinguish preflight, native generation, validation, and
  publication.

## Consequences

- Agents can distinguish a verified export from Aseprite's zero-exit or truthy-return
  false success.
- Existing-file behavior is deterministic and caller-controlled in headless runs.
- Native partial output is contained in an operation-owned temporary location until
  the complete expected export has passed validation.
- The Lua Kernel remains DRY authority for Export Operation behavior while Python
  performs ordinary process and filesystem adaptation.
- Multi-file atomicity and recovery are not speculative platform features; they can
  be revisited only from evidence in a concrete export workflow.

## Rejected alternatives

### Trust the Aseprite process exit code or Lua return value

Aseprite process and Lua return values do not prove that an Artifact exists or is
valid.

### Write directly to final paths

A Sprite Sheet can write metadata before its texture fails, and headless overwrite
confirmation is unavailable. Direct final writes would expose native partial or
unrequested replacement behavior to callers.

### Reimplement export or naming in Python

That would create a second authority for Aseprite rendering, selection, animation,
and Filename Format semantics. Python may map and verify files but cannot implement
the export itself.

### Build a generic transactional Artifact subsystem

The accepted workflows require truthful, explicit Export Destinations and verified
files. They do not require an Artifact Manifest, backup store, cross-command ledger,
or general rollback system.
