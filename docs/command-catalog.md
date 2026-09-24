# SPA command catalog

This catalog is the incremental, non-binding map of the Aseprite capability territory
that Aseprite Automation (SPA) can expose to agents. It records candidate Command Groups
and spellings as inputs to feature work. `spa` is the executable.

[`AUTHORITY_MATRIX.md`](../AUTHORITY_MATRIX.md) defines repository-wide ownership and
document dependencies. This catalog records exploratory candidates; it is not a task
tracker, release promise, schema registry, Capability Gap register, or statement of
shipped support. A candidate can change or disappear when a vertical slice produces
better Aseprite-aligned evidence.

## How to read this catalog

- Reuse Aseprite object and operation names when Aseprite already defines them.
- Treat a Command Group as navigation, not a Domain Module or Bounded Context.
- Keep inspection and validation beside the domain object they observe.
- Keep materially different native behaviors distinct, such as empty Frame addition, Frame duplication, Cel copy, and Cel link.
- Express each row as a candidate Operation intent, leaving fields, acceptance,
  dependencies, priority, evidence, and delivery status to their owning artifacts.
- Follow `CONTEXT.md` and accepted ADRs without restating their normative contracts.
- A feature issue can adopt, rename, split, combine, or reject a candidate. An
  Operation Descriptor owns an implemented public identity, and the installed Surface
  Manifest reports installed availability.

## Discovery and access

| Candidate command | Intended meaning |
| --- | --- |
| `spa info` | Report the selected Aseprite runtime, resources, version, supported capabilities, and Capability Gaps. |
| `spa version` | Report the installed SPA version. |
| `spa schema` | Emit the aggregate installed Surface Manifest. |
| `spa skill` | Emit or install Agent Skill guidance matched to the installed operation surface. |
| `spa <group> <command> --schema` | Emit one Operation's request, result, failure, and invocation schemas. |

## `sprite`

| Candidate command | Intended meaning |
| --- | --- |
| `spa sprite create` | Create a Sprite at an explicit Target Sprite File. |
| `spa sprite get` | Inspect requested dimensions, Color Mode, Frames, Tags, Palettes, Layer tree, Cels, Slices, Tilesets, and metadata. |
| `spa sprite set` | Change explicitly supported Sprite properties other than Color Mode or Color Profile. |
| `spa sprite copy` | Copy one Source Sprite File to an explicit Target Sprite File and verify the reopened result. |
| `spa sprite resize` | Resize the Sprite canvas with explicit scale and anchor semantics. |
| `spa sprite crop` | Crop the Sprite canvas to an explicit Rectangle or supported content rule. |
| `spa sprite flatten` | Apply Aseprite's native flattening behavior and report every affected Sprite structure. |
| `spa sprite change-color-mode` | Apply native Change Color Mode with explicit mapping, Palette, and Dithering inputs. |
| `spa sprite assign-color-profile` | Assign a native Color Profile without changing stored colors. |
| `spa sprite convert-color-profile` | Convert applicable pixels and Palette Entries through native Color Profile behavior. |
| `spa sprite validate` | Return typed Sprite structural Validation Findings. |

## `layer`

| Candidate command | Intended meaning |
| --- | --- |
| `spa layer list` | List the native Layer hierarchy and current address facts. |
| `spa layer get` | Inspect one exactly addressed Layer. |
| `spa layer add` | Add a regular Transparent or Group Layer; Tilemap creation belongs to its own slice. |
| `spa layer remove` | Remove one exactly addressed Layer and its subtree; reject Tilemap content in this slice. |
| `spa layer set` | Set name, visibility, or editability on a regular Transparent Image or Group; set opacity or blend mode only on a regular Transparent Image. |
| `spa layer move` | Reorder one regular Transparent Image or Group among its current parent's children. |
| `spa layer merge` | Merge one regular Transparent Image into its immediate lower regular Transparent Image sibling with Aseprite's experimental `new_blend=true` behavior. |
| `spa layer set-tileset` | Rebind one Tilemap Layer through explicit Tile mapping and Grid policies. |
| `spa layer convert-to-background` | Convert an eligible regular Transparent Layer to a Background Layer and report Cel normalization. |
| `spa layer convert-from-background` | Convert the Background Layer to a regular Transparent Layer. |

## `frame`

| Candidate command | Intended meaning |
| --- | --- |
| `spa frame list` | List Frames and persisted `duration_ms`. |
| `spa frame get` | Inspect one Frame Number and persisted duration. |
| `spa frame add` | Add an explicitly timed empty Frame. |
| `spa frame duplicate` | Duplicate one Frame with explicit copied-or-linked Cel behavior. |
| `spa frame set` | Set supported Frame properties. |
| `spa frame move` | Move one exactly addressed Frame to an explicit one-based insertion position and report shifted references. |
| `spa frame remove` | Remove exactly selected Frames and report shifted references. |

## `cel`

| Candidate command | Intended meaning |
| --- | --- |
| `spa cel list` | List Cels over bounded Layer and Frame targets. |
| `spa cel get` | Inspect one Cel's placement, opacity, link, and Image facts. |
| `spa cel add` | Add a Cel at an absent Layer/Frame intersection. |
| `spa cel clear` | Preserve a Cel while clearing it according to Layer kind. |
| `spa cel remove` | Remove eligible Cels and keep Background behavior explicit. |
| `spa cel set` | Set supported Cel properties. |
| `spa cel copy` | Copy Cel content to an explicit destination. |
| `spa cel link` | Link destination Cels to one native shared Image. |
| `spa cel unlink` | Replace a linked Cel with independent Image content. |

## `tag`

| Candidate command | Intended meaning |
| --- | --- |
| `spa tag list` | List Tags with current index, Frame Range, direction, and native repeats. |
| `spa tag get` | Inspect one Tag by current index or unique name. |
| `spa tag add` | Add a Tag with explicit Frame Range, direction, and repeats. |
| `spa tag set` | Set supported Tag properties and report its resulting facts. |
| `spa tag remove` | Remove one exactly addressed Tag. |

## `animation`

| Candidate command | Intended meaning |
| --- | --- |
| `spa animation audit` | Inspect animation coverage, timing, ranges, overlaps, and declared structural constraints. |
| `spa animation compare` | Compare two explicitly selected Frames and report objective pixel differences without publishing an Artifact. |
| `spa animation preview` | Export a two-Frame continuity-review PNG Preview Artifact to an explicit destination. |

## `image`

| Candidate command | Intended meaning |
| --- | --- |
| `spa image get` | Read a bounded Pixel Region Snapshot from an individual Cel Image or an explicit native Layer Composition. |
| `spa image replace` | Replace complete Image content from a compatible Snapshot. |
| `spa image import` | Import an external raster file into an explicit Sprite, Layer, Frame, or new native-object target. |
| `spa image resize` | Resize an Image with explicit algorithm and Cel-position policy. |
| `spa image crop` | Crop an Image to a contained Image Pixel Rectangle. |
| `spa image canvas-resize` | Reframe an Image without scaling through explicit placement and fill. |
| `spa image flip` | Mirror a whole eligible Image across an explicit axis. |
| `spa image rotate` | Rotate an eligible Image by an exact quarter turn. |

## `paint`

| Candidate command | Intended meaning |
| --- | --- |
| `spa paint apply` | Apply one canonical bounded Pixel Patch. |
| `spa paint composite` | Composite a Raster snapshot through explicit BlendMode, opacity, clipping, and Selection. |
| `spa paint line` | Draw one native Line-tool stroke. |
| `spa paint rectangle` | Draw an outlined or filled native Rectangle. |
| `spa paint ellipse` | Draw an outlined or filled native Ellipse. |
| `spa paint fill` | Invoke native Paint Bucket with explicit matching and bounds. |
| `spa paint pencil` | Draw one ordered native Pencil gesture. |
| `spa paint eraser` | Apply one ordered native Eraser gesture and behavior. |
| `spa paint spray` | Apply native-stochastic Spray when the runtime exposes its required inputs. |
| `spa paint gradient` | Apply native Linear or Radial Gradient when headless option control is complete. |
| `spa paint curve` | Apply native Four-Point Curve when its controller is scriptable. |
| `spa paint polygon` | Apply native Point-by-Point Polygon when its controller is scriptable. |
| `spa paint contour` | Apply one native filled Contour gesture. |
| `spa paint blur` | Apply deterministic native Blur Ink. |
| `spa paint jumble` | Apply native-stochastic Jumble when Pointer velocity and direction are scriptable. |

## `filter`

| Candidate command | Intended meaning |
| --- | --- |
| `spa filter brightness-contrast` | Apply native Brightness/Contrast through explicit Channels and Filter Application. |
| `spa filter hue-saturation` | Apply native HSL/HSV adjustment through explicit modes and Channels. |
| `spa filter color-curve` | Apply native Color Curve Points to explicit component or Index Channels. |
| `spa filter replace-color` | Apply native per-component or stored-Index matching. |
| `spa filter invert-color` | Apply native component or stored-Index inversion. |
| `spa filter outline` | Apply native Outline with explicit placement, matrix, colors, Channels, and Tiled Mode. |
| `spa filter convolution-matrix` | Apply one native named Convolution Matrix Resource when the runtime honors its contract. |
| `spa filter despeckle` | Apply native per-channel Median Filter behavior. |

## `palette`

| Candidate command | Intended meaning |
| --- | --- |
| `spa palette list` | List Palette Changes and their effective Frame Ranges. |
| `spa palette get` | Resolve a Frame to its Effective Palette and entries. |
| `spa palette set` | Recolor entries in one existing Palette Change. |
| `spa palette reorder` | Reorder entries with an explicit scope and pixel-index mapping. |
| `spa palette remap` | Apply Sprite-wide Remap Colors through an explicit mapping. |
| `spa palette resize` | Resize an existing Palette under explicit entry-use rules. |
| `spa palette import` | Import entries into an existing Palette Change. |
| `spa palette export` | Export one Effective Palette as a verified Artifact. |
| `spa palette color-quantization` | Replace an existing Palette through native Color Quantization. |

## `selection`

| Candidate command | Intended meaning |
| --- | --- |
| `spa selection create` | Create a normalized explicit Selection value. |
| `spa selection combine` | Union, intersect, subtract, or xor Selection values. |
| `spa selection invert` | Invert a Selection inside an explicit Canvas Rectangle. |
| `spa selection grow` | Grow a Selection through declared native semantics. |
| `spa selection shrink` | Shrink a Selection through declared native semantics. |
| `spa selection transform` | Transform a Selection without moving Sprite pixels. |
| `spa selection validate` | Validate encoding, bounds, and Coordinate Space. |
| `spa selection export` | Export canonical Selection data as a JSON Artifact. |
| `spa selection preview` | Produce a non-authoritative image Preview Artifact. |

## `slice`

| Candidate command | Intended meaning |
| --- | --- |
| `spa slice list` | List Slices with complete ordered Key facts and effective Frame Ranges. |
| `spa slice get` | Inspect one Slice by current index or unique name. |
| `spa slice add` | Add a Slice with one initial Key at Frame 1. |
| `spa slice set` | Set supported Slice properties under explicit Key constraints. |
| `spa slice remove` | Remove one exactly addressed Slice. |

## `tileset` and `tilemap`

| Candidate command | Intended meaning |
| --- | --- |
| `spa tileset list` | List Tilesets and referencing Tilemap Layers. |
| `spa tileset get` | Inspect Grid, Base Index, properties, Tiles, keys, and indexes. |
| `spa tileset add` | Add a named Tileset with explicit Grid and Base Index. |
| `spa tileset set` | Set supported writable Tileset properties. |
| `spa tileset remove` | Remove one unreferenced Tileset. |
| `spa tileset resize` | Replace a Tileset under explicit image, Grid, Cel, and placement policies. |
| `spa tileset tile get` | Inspect a Tile by key or current index. |
| `spa tileset tile add` | Append a keyed non-empty Tile from typed Image input. |
| `spa tileset tile set-key` | Assign or change one Tile Key explicitly. |
| `spa tileset tile set` | Set a keyed Tile's Image or native properties. |
| `spa tileset tile remove` | Remove a Tile and explicitly rewrite affected placements. |
| `spa tileset tile reorder` | Reorder every keyed non-empty Tile through a complete permutation. |
| `spa tileset validate` | Validate Grid, references, indexes, keys, and Tile rules. |
| `spa tilemap get` | Inspect topology or one bounded Tile Region Snapshot. |
| `spa tilemap set` | Replace a complete Tile Cell Rectangle. |
| `spa tilemap patch` | Change listed Tile Cells and preserve the rest. |
| `spa tilemap fill` | Fill a bounded Tile Cell Rectangle. |
| `spa tilemap validate` | Validate bounds, references, Coordinate Spaces, and layout rules. |

## `export`

| Candidate command | Intended meaning |
| --- | --- |
| `spa export image` | Export one Frame and Layer Composition as a verified raster Artifact. |
| `spa export sheet` | Export sprite-sheet image and typed metadata Artifacts. |
| `spa export gif` | Export an animated GIF Artifact. |
| `spa export sequence` | Export an ordered bounded Frame image collection. |
| `spa export tileset` | Export Tileset image and normalized metadata Artifacts. |

## `plan`

| Installed command | Intended meaning |
| --- | --- |
| `spa plan check` | Validate a bounded single-Sprite Operation Plan without opening Aseprite. |
| `spa plan run` | Execute eligible Steps in one Aseprite process and commit at most one target. |

## `script`

| Candidate command | Intended meaning |
| --- | --- |
| `spa script run` | Execute exact caller-owned Lua under the documented trust boundary. |

## Unresolved candidate groups

Rasterized text remains candidate product territory. The catalog does not propose a
`text` group until feature work establishes an Aseprite-aligned operation boundary.
