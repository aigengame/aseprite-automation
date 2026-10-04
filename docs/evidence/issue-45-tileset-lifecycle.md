# Tileset lifecycle native evidence

[#45](https://github.com/aigengame/aseprite-automation/issues/45) owns standalone
rebind/remove and Plan composition. The owner moved resize to
[#175](https://github.com/aigengame/aseprite-automation/issues/175) on 2026-10-04
after the preservation experiment below. ADR-0047 owns the shared design direction.
This record is evidence, not a compatibility promise or feature authority.

## Scoped resize prerequisite

Local macOS Aseprite `1.3.18.5-dev`, Lua API 41, was checked against source
`375989a61c3425cd4e8cdedfcfcca4bdfef7e1d9`. The final prepared invocation exited 0;
all four cases completed without a crash. A macOS NSWorkspace notification diagnostic
was present on stderr. Linux and a complete resize Operation were not verified.

Retained evidence:

- [One-time Lua experiment](issue-45-resize-probe.lua).
- [Native observations](issue-45-resize-native.json).
- [Marker counts in files saved and reopened by Aseprite](issue-45-resize-markers.json).

The experiment takes `--script-param output=/absolute/existing/scratch/directory`.
Run it with `--batch --script` in an isolated invocation. On local packaged macOS
builds, use `spa.adapters.aseprite.invocation.prepare_invocation()` for the existing
launch/data/preferences setup. It is not part of routine capability discovery or CI.
For the marker check, count the bytes of
`SPA45_NATIVE_TILE_ZERO_OPAQUE_SENTINEL` in the four `zero-*.aseprite` files.
Only read the native-created files; do not change their bytes.

| Public native path | Observation |
| --- | --- |
| Same-Sprite Tileset clone | Retains the old Grid. Cross-Sprite cloning rejects. |
| Base Index, Tile 0 text/color setters | Restore those resets and persist after save/reopen. The resets alone are not an unresolved gap. |
| `SpriteSize` | Changes all Tilesets, ordinary Images, Cel positions, canvas, Selection, and Slice keys. No selected-Tileset argument. |
| Actual Tile 0 Properties | Unique marker: original 1; cloned 2; resized plus text/color/Base Index restoration 0; reopened/resaved 0. |
| Layer range Copy/Paste in batch | Range can be selected, but Copy and Paste return false and transfer no Tileset. |

The Tile 0 Properties getter aliases Tileset properties at this native boundary:
`doc::notile` is 0, and `Properties::properties()` chooses Tileset UserData for that
value. Thus the earlier getter-based observation could not prove actual Tile 0
preservation. The table setter can write real Tile 0 data; the marker experiment
observes its loss independently. `cmd_sprite_size.cpp` copies TileData only for
nonzero Tile indexes.

Selected nonzero Tile and Tileset plugin int64, Point, binary-string, and text values
survived the tested paths. This sample does not establish complete metadata transfer.
The inspected clone/resize source also omits match/external-link fields; those
source-only observations were not given independent native fixtures here.

The tested paths do not meet scoped replacement and preservation requirements.
This does not prove permanent impossibility. The accepted response is to defer
callable resize, retain its feature contract in #175, and revisit verified native
capabilities. No property serializer, native-file repair, broad restore engine, or
metadata registry was added to compensate.

## Rebind and remove

`Layer.tileset` changes the native reference without remapping Tile indexes.
SPA resolves every used Key and validates the complete requested mapping first.
It constructs one replacement Image per original Linked Image, preserving native
flags for keyed destinations and writing packed zero for explicit Empty.

Changing the Layer reference does not refresh cached Cel Canvas bounds. Replacing
the Image after setting the new Tileset lets the native API compute bounds from the
new Grid. With a changed Grid this refresh is needed even if the packed values do
not change. Cel Canvas positions, Tile Cell dimensions, and Linked Cels remain intact.
This was verified through native save/reopen with a second Layer sharing the old
Tileset left unchanged.

An orphan removal targets that exact native Tileset. The native reindexing of
surviving Tilesets is reported. A referenced removal is refused before mutation;
SPA does not use Aseprite's implicit reassignment to collection index 0.

The installed capability probe tests those public paths and rollback using a small
native document. Feature tests add complete used-Key mapping, Indexed usage-Frame
Palette checks, public Plan composition, preservation of an existing Target after
failure, and an independent native oracle. Current evidence is local macOS only
until a Linux run is recorded for the implementation PR.
