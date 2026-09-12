# ADR-0085: Define the Export publication boundary

## Status

Accepted

## Context

Aseprite's headless save and export seams do not by themselves prove that every
requested file was produced correctly. A native operation can overwrite a destination,
return success without the requested file, or leave one part of a multi-file output
without its counterpart. An agent therefore needs an explicit and independently
verified publication boundary.

This requirement does not justify a general transaction, backup, recovery, provenance,
or Artifact-registry subsystem.

## Decision

- Every Export Operation declares its final Export Destinations and existing-file
  intent. It does not inherit an editor prompt, preference, recent-file state, or an
  implicit overwrite default.
- Before native execution, the Operation resolves its complete bounded expected output
  set. Empty expansions, duplicate or colliding destinations, unsupported naming, and
  incompatible existing-file intent fail before export.
- The file adapter maps final destinations to an operation-owned staging location. The
  fixed Lua Operation Kernel remains the authority for native selection, rendering,
  conversion, encoding, and Aseprite Filename Format behavior; Python does not become
  an alternate exporter.
- A native return value or process exit code is not proof of completion. SPA requires
  the private Kernel Response and independently validates every expected staged file
  against the owning Operation's declared format and semantic facts.
- SPA starts final publication only when the complete expected output set has passed
  validation. A successful Result reports every final file through the simple Artifact
  contract defined by ADR-0013.
- When an Export has several final paths, the file adapter publishes them in a
  deterministic order. A failure before the first final-path change is an ordinary
  publication failure. A failure after one or more paths changed returns the stable
  `PARTIAL_PUBLICATION` Failure Code and code-specific details for every declared
  destination: role, normalized path, whether it existed before publication, and a
  state of `published`, `not_published`, or `indeterminate`. A `published` destination
  also states whether it replaced an existing file. The Operation returns no success
  Result or successful Artifact set.
- SPA does not automatically restore replaced files or remove already published files.
  A hard interruption that prevents a Failure Envelope also prevents SPA from claiming
  a known publication outcome; a later request applies its declared `if_exists` policy
  to the paths that actually exist.
- Export does not mutate the Source Sprite and is not a Plan Step. Staging an export is
  distinct from the Staged Sprite File and Target Commit used by Sprite Mutations.
- This boundary does not promise filesystem atomicity across several final paths. A
  concrete Export Operation can strengthen its publication behavior only when its
  feature issue demonstrates that functional need; the requirement does not create a
  general recovery framework.

## Consequences

- Agents can distinguish a verified export from native false success or partial output.
- Existing-file behavior and the expected file set are explicit before Aseprite runs.
- A caller can distinguish failure before publication from known or indeterminate
  partial publication and can see which existing destinations were replaced.
- Native behavior stays in the Lua Kernel while ordinary path mapping, file inspection,
  and publication stay in the application and file adapters.
- Each export feature owns its format-specific contract without duplicating this shared
  publication boundary.

## Rejected alternatives

### Trust native success or write directly to final paths

Neither proves that the requested complete Artifact set exists, and direct writes expose
native replacement and partial-output behavior to callers.

### Reimplement export behavior in Python

That would create a second authority for Aseprite rendering, selection, conversion,
encoding, and Filename Format semantics.

### Build a general transactional Artifact subsystem

Current workflows require truthful publication of declared outputs, not a registry,
backup store, provenance history, or cross-command recovery service.
