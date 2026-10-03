# Tile lifecycle native evidence

Issue [#43](https://github.com/aigengame/aseprite-automation/issues/43) owns this
delivery contract. ADR-0041 owns identity; ADR-0044 owns Placement meaning. This
record explains the implementation mechanism, not a broader compatibility promise.

## Baseline and observations

Bounded probes on macOS Aseprite `1.3.18.5-dev`, API 41, used public batch scripting.
Source inspection used Aseprite commit `375989a61c3425cd4e8cdedfcfcca4bdfef7e1d9`.

| Native path | Observed behavior | SPA use |
| --- | --- | --- |
| `Sprite:newTile` | Appends a nonzero Tile; unrelated indexes stay unchanged. | Supply complete matching Pixel Region Snapshot and caller Key. |
| `Tile.properties("aigengame.spa").tile_key` | Persists the Key without replacing other namespaces. | Assign only a missing Key. |
| `app.command.MoveTiles` | Moves the complete native Tile record but does not remap Tilemap Images. | Compute one complete old-to-new mapping before native mutation. |
| `Sprite:deleteTile` | Removes the record; subsequent indexes shift; Tilemap Images do not change. | Resolve explicit replacement in its final index space. |
| `Cel.image = image` | Replaces all references to the original native Image, retaining Linked Cels. | Snapshot each original Image and write its mapped content once. |

`src/app/util/cel_ops.cpp` implements MoveTiles with `RemapTileset`; it does not run
the editor's complete `RemapTilemaps` workflow. Treating the native operation as a
complete Tile lifecycle change would silently reinterpret existing indexes.
Direct `.properties` assignment only handles the selected namespace. SPA therefore
moves native records instead of transferring metadata through #41's observation JSON.

The bounded native probes and committed tests cover int64 values beyond JSON's exact
number range, Point values, binary strings, default/SPA/plugin namespaces, Tile text,
color and Image content, cross-Layer references, Linked Cels, and save/reopen.
These examples verify the chosen native transfer mechanism; they do not claim that
Lua can enumerate every namespace or reconstruct file storage types.

For an orphan Tileset, native MoveTiles needs a temporary Tilemap Layer. The transaction
binds that Layer to the exact orphan, removes only the newly generated implicit
Tileset, reorders, and removes the temporary Layer. Whole-document checks verify that
no unrelated Layer, Cel, Frame, Tileset, or link changes remain. A transaction-error
probe also verified restoration of native Tile order and original placements.

## Public validation

An additional RGB/Grayscale probe tested five public Tile Image write paths per
mode with Alpha 0 and nonzero hidden color channels. `Tile.image=` and `putPixel`
normalize immediately. `image.bytes=`, `clear`, and `pixels()` can retain the bytes
in memory, but reopening normalizes them. The cause is
`Tileset::set/add/insert` calling `preprocess_transparent_pixels`; the file decoder
also calls `Tileset::set` for each Tile. Changing the write method cannot satisfy
a byte-preserving save/reopen contract for those inputs. Transparent zero-channel
pixels and Indexed Transparent Color Index content remain valid native Tiles.
The current publication guard detects the mismatch and refuses to publish it.
Issue #43 remains the authority for any input-scope decision based on this evidence.

`tests/tile/test_e2e_lifecycle.py` invokes installed public Operations, then uses a
separate native oracle to inspect saved results. A Layer UUID first assigned during
save is reported from the reopened Sprite. The ordinary persistence verifier retains
authority for document facts; Tile lifecycle adds content/order and Placement checks.

Tile record postconditions inspect the selected Tileset. Public native lifecycle
operations act on that exact Tileset; SPA does not hash every unrelated Tile Image
on each invocation. The shared document verifier checks document structure, all Cel
Images, and links. Independent native oracle assertions verify unrelated Tileset
pixels, Keys, data, and opaque Properties, including the orphan reorder path. These
tests do not claim runtime hashing of unrelated Tile content on every Operation.

Run the same selection on local macOS and Linux:

```sh
SPA_TEST_ASEPRITE=/absolute/path/to/aseprite \
  uv run --frozen --group test pytest tests/tile -m 'e2e and not slow'
```

Platform-specific execution results belong in the PR. Local evidence alone does not
establish Linux verification. Future accepted native paths can change these mechanics
without adding a metadata registry, emulation engine, or compatibility platform.
