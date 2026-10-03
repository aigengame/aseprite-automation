# Issue #40: complete Slice reads and bounded native authoring

## Authority and environment

Issue #40 owns delivery scope; ADR-0039 owns the Slice model and addressing.
Local evidence uses macOS Aseprite `1.3.18.5-dev`, API 41, Lua 5.4. Native source
inspection uses commit `375989a61c3425cd4e8cdedfcfcca4bdfef7e1d9`.
Linux results belong to the exact PR CI run and are not inferred from macOS.

## Observation and mutation boundaries

| Native observation | SPA behavior and retained evidence |
| --- | --- |
| Public Lua Slice getters expose the first Key. Setters write native Frame 0, even with another active Frame. | Complete reads use private native `ExportSpriteSheet` metadata. Bounds, center, and pivot setters require exactly one explicit Key at public Frame 1. Tests reject multi-Key and late-starting geometry before publication. |
| Export emits every explicit Key in native Frame order. | The Lua reader validates JSON object/array shapes, integral geometry, strictly ordered distinct Frames in range, and text/color agreement with the open Sprite. It converts Frames to one-based facts and reports exact effective ranges without filling before the first Key. |
| New Slices enter the front of the live collection. Native save/reopen can reverse collection order. Duplicate names are valid. | Name targeting requires exactly one match; index targeting uses the Source snapshot. All mutations return the full reopened indexed collection. `previous_slice` on set/remove is explicitly a Source snapshot fact, never an address in the Target. |
| Bounds are in Canvas Pixel space; center/pivot are relative to bounds' top-left. | Negative positions remain valid. Add and geometry set require positive dimensions so a zero-size bounds setter cannot silently delete a Key. Reads preserve zero-size native Rectangle facts. |
| `center=nil` clears the center; `pivot=nil` stores Point(0,0). | Explicit `center:null` clears; omitted properties preserve. Pivot clearing is absent and explicit `pivot:null` is rejected. The Surface Manifest reports the limitation. |
| Native transparent user-data Color canonicalizes to RGBA(0,0,0,0). | Results contain reopened native text/color facts. Metadata-only edits preserve all Keys; custom Slice properties remain native-owned and are checked by a retained native fixture. |
| No public non-interactive API for arbitrary Key add/set/remove passed acceptance. | No arbitrary Key mutation descriptors are registered. The runtime capability probe verifies only whole-Slice add, static set, center clear, and remove after save/close/reopen. Future extension requires new evidence, not a permanent prohibition. |

The packaged Slice owner checks the requested live mutation, unrelated shared
snapshot facts, Cel Image content, and persisted Slice facts before Target Commit.
The shared persistence equivalence excludes RGB/Grayscale Palette facts. Tileset
snapshots contain structural facts, not Tile bitmap bytes. Shared persistence
compares Slice collections by complete fact multiplicities, including ordered
Keys, without assuming collection order. File publication reuses the shared
staging and Source/Target identity lifecycle.

## Exporter failures remain failures

The reader removes any earlier private JSON before each export, requests no
texture output, uses explicit export options, and restores editor state. A native
command that returns without writing cannot reuse a stale successful observation.
Malformed or incomplete metadata fails the whole operation; there is no fallback
to the first Key, JSON repair, or partial success.
The first exported Key's bounds, center, and pivot must also agree with public
Lua getters. This catches omitted first geometry as well as structural errors.
Later Key values rely on native export; public Lua does not provide a second
complete Key collection for independent equality checks. SPA validates their
shape, ordering, and timeline coverage without adding private file parsing.

On this native version, Slice text containing a line feed is written into vendor
JSON without the required escape. The retained LF fixture proves that native
export returns and SPA decoding rejects the malformed output. Reads and writes
that encounter this defect fail; mutation failure preserves the Source and
existing Target. SPA does not promise to repair the native exporter.

A native in-memory Slice can have no Keys. Reads accept an absent/empty Key list
only when native `bounds` is nil. Native save can omit that Slice; persistence
checks must not report this loss as successful preservation.

## Retained tests and source pointers

- `tests/slice/test_e2e_slice.py`: installed CLI semantics and Target publication.
- `tests/slice/test_e2e_vendor.py`: real exporter, fault injection, stale data,
  keyless observation, and malformed native LF output.
- `tests/runtime/test_e2e_aseprite.py`: installed capability and gap discovery.
- `tests/sprite/test_e2e_sprite_persistence.py`: shared Slice collection equality,
  ordered Keys, duplicate multiplicities, and native Tag mutation across Slice
  reordering.
- `src/app/script/slice_class.cpp`, `sprite_class.cpp`, `userdata.h`: public native
  Slice properties, creation/deletion, and metadata.
- `src/doc/slices.cpp`, `src/app/cmd/set_slice_key.cpp`: collection and Key changes.
- `src/app/doc_exporter.cpp`: complete Key metadata and text escaping.
- `src/dio/aseprite_encoder.cpp`, `aseprite_decoder.cpp`: persistence order and Keys.

The multi-Key test fixture adds native Slice chunks only to construct otherwise
unreachable input. This is test preparation, not a product mutation mechanism.
