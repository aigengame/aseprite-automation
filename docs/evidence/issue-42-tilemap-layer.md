# Tilemap Layer creation: native persistence evidence

## Scope and baseline

Issue #42 extends `layer add` with explicit Tileset create/share intent. These
bounded experiments establish native premises, not delivered SPA acceptance.

- Observed on 2026-10-03, local macOS Aseprite `1.3.18.5-dev`, API 41.
- Each persistence case saves a native `.aseprite` file, closes the Sprite, opens
  the file again, and reads the native properties.
- Source cross-check: local Aseprite revision
  `375989a61c3425cd4e8cdedfcfcca4bdfef7e1d9`. This identifies the inspected source,
  not a claim that this commit built the installed application.
- Linux and other runtime versions were not tested by these experiments.

## Grid alternatives

| Native path | Result |
| --- | --- |
| `NewLayer { tilemap=true, ask=false, gridBounds=Rectangle(0,0,4,5) }` | Tile size 4 by 5 and origin (0,0) persist. The initial ordinary Layer and Sprite Grid remain unchanged; the new Layer has no Cels. |
| The same command with origin (2,-3) | The live Tileset reports (2,-3); reopening reports (0,0). |
| `Sprite:newTileset(Grid { x=2,y=-3,width=4,height=5 })` | Native rejection: a Tileset with a nonzero origin cannot be created. |
| `Sprite:newTileset(Rectangle(2,-3,4,5))` | The same native rejection. |
| Assign `Tileset.grid` | Native rejection: the property has no setter. |
| `Sprite:newTileset(existingTileset)` with a live nonzero origin | Both original and copied Tilesets retain (2,-3) in memory and reopen at (0,0). |
| Set `Sprite.gridBounds=(2,-3,4,5)` and use default `NewLayer` Grid | Sprite Grid persists; Tileset Grid origin still reopens at (0,0). These are distinct facts. |
| Zero-origin Tileset and Tilemap Cel at position (2,-3) | Both Tileset Grid and Cel position persist. This is Cel placement, not storage of a nonzero Tileset origin. |

The public Lua constructor explicitly rejects a nonzero Tileset origin in
`src/app/script/sprite_class.cpp:612`. `src/app/script/tileset_class.cpp` registers
only a Grid getter. The encoder writes Tile dimensions but no Grid origin in the
Tileset chunk (`src/dio/aseprite_encoder.cpp:1090`); the decoder constructs
`Grid(Size(width,height))` (`src/dio/aseprite_decoder.cpp:1241`). Embedded and
external Tilesets share this header. Another construction path does not change
that persistence representation.

Cel placement is a usable native mechanism for translating rendered Tilemaps:
`src/doc/cel.cpp` adds Cel position to the Tileset Grid. Issue #42 creates an empty
Layer, so it must not silently create a Cel or reinterpret a Tileset input as Cel
placement.

## Base Index alternatives

The public setter accepts values that the file cannot retain. Observed examples:

| Requested/live Base Index | Reopened Base Index |
| --- | --- |
| -32769 | 32767 |
| -32768 | -32768 |
| 77 | 77 |
| 32767 | 32767 |
| 32768 | -32768 |
| 65535 | -1 |
| 65536 | 0 |
| 2147483647 | -1 |

The [native file specification](https://github.com/aseprite/aseprite/blob/375989a61c3425cd4e8cdedfcfcca4bdfef7e1d9/docs/ase-file-specs.md#tileset-chunk-0x2023)
defines Base Index as `SHORT`. The encoder casts to `short` and the decoder reads
the same signed 16-bit value. No separate native save path was found that keeps
an out-of-range Base Index with the same meaning.

## Decision separation

After reviewing these alternatives, the owner accepted this creation boundary:
retain the full Grid input shape, require origin (0,0) and signed 16-bit Base Index,
declare both constraints in the schema, and reject violations before launching
Aseprite. Do not compensate by changing native meaning or creating Cels.

These results establish current native persistence limits. The issue owns the
accepted request and refusal contract. Neither storing custom properties nor
altering Tile indexes would preserve the requested native property. Future
accepted requirements and verified native changes can extend the delivery scope;
this evidence does not establish a permanent product prohibition.
