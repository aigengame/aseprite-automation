# Sprite Automation

SPA's business capability is coextensive with Aseprite's. It provides agent-facing automation for sprite creation, editing, validation, conversion, and export, including the control, composition, observation, and verifiable feedback that make those capabilities effective for agents. It uses Aseprite's public editor and scripting terms for concepts that Aseprite already names, and defines new terms for the agent automation contract rather than a new creative domain.

## Language

### Aseprite model

**Sprite**:
The complete editable pixel-art or animation object, including its layers, frames, cels, tags, palettes, slices, selection, and tilesets. A Sprite can exist without an associated file.
_Avoid_: Sprite Document, document, canvas, image, asset

**Image**:
An Aseprite pixel buffer used by a Cel or as an intermediate raster value. An Image owns pixel data and dimensions but not the Cel's Layer/Frame membership or position; linked Cels can share the same Image.
_Avoid_: Sprite, Cel, canvas, exported image file

**Cel**:
The native Aseprite object at one Layer and Frame intersection. A transparent image or tilemap Layer can have no Cel at an intersection; this absence is distinct from a Cel whose Image currently contains no visible content.
_Avoid_: Frame, Image, empty pixel buffer, implicit Layer/Frame slot

**Background Layer**:
The single native non-transparent Image Layer a Sprite can contain. It has a full-canvas Cel at every Frame; converting a Layer to Background normalizes Cel position and opacity, fills transparent or missing areas with a Background Color, and creates missing Cels.
_Avoid_: bottommost Layer, transparent Image Layer, canvas color setting

**Background Color**:
The explicit Color Value used when converting a Layer to Background or clearing a Background Cel. SPA does not obtain it from hidden editor foreground/background color state or preferences.
_Avoid_: Transparent Color Index, implicit editor color, Layer color label

**Color Mode**:
The native Aseprite Sprite pixel representation: RGB, Grayscale, or Indexed. It determines how Image pixel values are encoded and interpreted.
_Avoid_: Color Profile, palette, file format

**Color Profile**:
The native Aseprite description of how a Sprite's stored color values are interpreted. Aseprite's Lua API represents it with a `ColorSpace` value that can contain no profile, sRGB, or an ICC profile. Color Profile is independent of Color Mode.
_Avoid_: Color Mode, hidden working profile, display or monitor profile, generic color-management policy

**Assign Color Profile**:
The native Aseprite Sprite operation that replaces the Color Profile without changing stored Image pixels or Palette Entries. It changes their interpretation rather than their values.
_Avoid_: Convert Color Profile, implicit export tagging, display conversion, pixel edit

**Convert Color Profile**:
The native Aseprite Sprite operation that transforms applicable Image pixels and Palette Entries to a target Color Profile so their appearance is preserved, then assigns that profile. SPA delegates the complete behavior to Aseprite and reports any runtime-specific coverage limits.
_Avoid_: Assign Color Profile, Change Color Mode, Python color transform, hidden working profile

**Change Color Mode**:
The native Aseprite Sprite-wide operation, exposed to scripts as `ChangePixelFormat`, that changes RGB, Grayscale, or Indexed pixel representation. Its applicable Effective Palette, RGB Map Algorithm, Color Best Fit Criteria, Grayscale, and Dithering inputs depend on the source and target Color Modes. It does not generate a Palette. SPA uses the same fixed Lua Kernel behavior for `sprite change-color-mode` and for a disposable export Sprite.
_Avoid_: Color Conversion framework, generic property set, Python pixel conversion, implicit preferences

**Alpha Channel**:
The native transparency component of an RGB or Grayscale Image pixel. Indexed transparency instead uses the Sprite's Transparent Color Index and can also involve alpha values on Palette Entries; SPA does not collapse these mechanisms into a universal Alpha policy.
_Avoid_: Transparent Color Index, Background Color, universal transparency mode

**File Format**:
An Aseprite-native encoder/decoder capability associated with filename extensions and supported image properties. An Export Operation declares a typed File Format branch and its native options; the owning command constrains whether it produces a single image, animation, metadata, or another file role.
_Avoid_: Static Image Format, filename extension alone, generic options dictionary

**Palette Index**:
The native integer value stored by an Indexed Image pixel to refer to an entry in the Palette applicable to its Frame. It is not an RGBA Color and must be interpreted with that Palette.
_Avoid_: packed pixel color, Tile Index, universal color ID

**Palette Entry**:
One zero-based slot in a Palette, pairing a Palette Index with an RGBA color. Changing an Entry color while preserving pixel indexes intentionally recolors every applicable Indexed pixel that stores that index.
_Avoid_: Color identity, independent swatch object, pixel color copy

**Palette Change**:
A Palette stored at a one-based `palette_frame_number` from which its entries take effect. Palette Changes are ordered by Frame Number. SPA can inspect and edit an existing Palette Change, while creation and deletion remain an explicit Capability Gap in Aseprite 1.3.18.5's public Lua/editor surface.
_Avoid_: Palette ID, Palette collection index, per-Frame Palette copy, implicit lifecycle mutation

**Effective Palette**:
The Palette Change resolved for a requested `frame_number`: the latest Palette Change at or before that Frame. It applies through the Frame immediately before the next Palette Change, or through the Sprite's last Frame.
_Avoid_: active editor Palette, independent Frame Palette, Palette identity

**Current Palette**:
The native Aseprite editor term for the Palette shown for the active Frame. SPA does not use mutable editor state as a public address; it resolves the same persisted Palette through an explicit Frame's Effective Palette or an exact `palette_frame_number`.
_Avoid_: implicit active Palette, first Palette, Palette identity

**Color Quantization**:
The native Aseprite operation named "Create Palette from Current Sprite (Color Quantization)" that renders all Sprite Frames with the declared New layer blending method, generates a bounded Palette value, and applies it to the Current Palette. SPA exposes it through an exact existing Palette Change and keeps it distinct from Change Color Mode.
_Avoid_: Palette Source, implicit Indexed conversion, custom quantizer, Palette Change creation

**RGB Map Algorithm**:
The native Aseprite algorithm choice used to generate a Palette during Color Quantization or map RGBA colors to Palette Indexes during Change Color Mode. The Published Language field is `rgb_map_algorithm`; its values are the documented `default`, `rgb5a3`, and `octree`. On Aseprite 1.3.18.5 explicit `default` resolves to Octree and is distinct from an omitted preference-derived value.
_Avoid_: generic quantizer, implicit preference, unknown-value fallback, Python color map

**Color Best Fit Criteria**:
The native Aseprite criterion used when choosing the Palette Entry that best matches a color. The Published Language field is `color_best_fit_criteria`; its values are the documented `default`, `rgb`, `linearizedRGB`, `ciexyz`, and `cielab`. Explicit `default` selects Aseprite's own Default criteria and is not omission or an alias invented by SPA.
_Avoid_: Best-fit policy, generic color distance, implicit preference, renamed color space

**Remap Colors**:
The native Aseprite Sprite-wide operation of rewriting all Indexed Image pixel values through an explicit old-to-new Palette Index mapping, including the Sprite's Transparent Color Index where applicable. It is distinct from changing Palette Entry colors and never has a Frame or Palette Change scope.
_Avoid_: automatic nearest color, ranged remap, Palette reorder, RGBA replacement

**Transparent Color Index**:
The Palette Index exposed by Aseprite as `Sprite.transparentColor` that represents transparency on transparent Layers of an Indexed Sprite. It is distinct from an RGBA or Grayscale alpha channel.
_Avoid_: alpha, transparent RGBA value, background color

**Point**:
An Aseprite-aligned integer `x`, `y` position interpreted in the Coordinate Space declared by its Operation. The origin is zero-based at the top left of that space; the same numbers in different spaces are not interchangeable.
_Avoid_: unqualified coordinates, Frame position, implicit active-site point

**Rectangle**:
An Aseprite-aligned `x`, `y`, `width`, `height` value. It covers the half-open region from `x` through `x + width` and `y` through `y + height`, excluding the upper endpoints. Width and height are non-negative; either being zero makes the Rectangle empty.
_Avoid_: right/bottom endpoints, inclusive maximum coordinates, negative size

**Slice**:
A named native object contained by a Sprite. A Slice owns ordered Slice Keys and user data; its geometry can therefore vary over the animation timeline rather than being one static Rectangle.
_Avoid_: static export rectangle, Selection, Sprite child with persistent ID

**Slice Key**:
The explicit value of a Slice beginning at a one-based `frame_number`. It contains `bounds` in Canvas Pixel space, an optional `center` Rectangle relative to the Slice Bounds, and an optional `pivot` Point relative to the Slice Bounds. A Key remains effective from its Frame through the Frame immediately before the next Key, or through the Sprite's last Frame. Inspection preserves every explicit Key and reports its inclusive effective Frame Range. Aseprite 1.3.18.5 exposes these complete Keys through native exporter metadata but not through the public Lua Slice collection; arbitrary Key creation, mutation, and deletion are therefore a Capability Gap for that runtime.
_Avoid_: flattened Slice bounds, zero-based public key frame, keyframe ID

**Slice Index**:
The current one-based position of a Slice in `Sprite.slices`, exposed as `slice_index`. Aseprite can change collection positions when Slices are added, so this is a current-snapshot address rather than a Persistent Identity.
_Avoid_: Slice ID, stable Slice position, zero-based slice index

**Tileset**:
A native Sprite-contained collection of Tiles with one Grid, name, Base Index, and user data. One Tileset can be referenced by multiple Tilemap Layers, and a Sprite can also contain a Tileset that no Layer currently references.
_Avoid_: Tilemap Layer, exported tile sheet, Tile collection owned by one Cel

**Tileset Index**:
The current one-based position of a Tileset in `Sprite.tilesets`, exposed publicly as `tileset_index`. Aseprite's internal and file-format references use zero-based collection positions and are converted inside the Lua Operation Kernel. Collection mutation can change the position, so it is not a Persistent Identity.
_Avoid_: `.aseprite` tileset ID, Tileset UUID, stable collection position

**Tile**:
A native element of one Tileset containing a tile-sized Image and user data. A Tile's current position is its Tile Index; Aseprite exposes no independent persistent Tile ID.
_Avoid_: Tilemap cell, Tile Placement, raster pixel

**Tile Index**:
The native zero-based position of a Tile inside its Tileset and the value encoded by Tile Placements. Index 0 is the Empty Tile. Insertion, deletion, or reorder can change later indexes, so a Tile Index is an observation rather than a Persistent Identity.
_Avoid_: Tileset Index, Base Index, Tile Key, one-based tile position

**Empty Tile**:
The mandatory Tile at Tile Index 0 that represents no tile content in Aseprite. It cannot be removed and has no Tile Key.
_Avoid_: transparent user Tile, absent Cel, null Tile Key

**Base Index**:
The persisted Aseprite Tileset display offset exposed by Lua as `Tileset.baseIndex` and publicly by SPA as `base_index`. Aseprite displays a Tile numbered `tile_index + base_index - 1`; the value does not change the Tile Index encoded in a Tilemap and is never an address or identity.
_Avoid_: Tile Index, Tileset Index, placement value, persistent Tile ID

**Tilemap Layer**:
The native Aseprite Layer kind whose Cels contain Tilemap Images and which references exactly one Tileset. Multiple Tilemap Layers can share the same Tileset. Like other Cel-bearing Layers, a Tilemap Layer can have no Cel at a Frame.
_Avoid_: Tileset, flattened raster Layer, mandatory Cel on every Frame

**Tilemap Layer Tileset Intent**:
The required discriminated part of `layer add` when `kind` is `tilemap`: `create` declares a new named Tileset with its Grid and Base Index, while `share` exactly addresses an existing Tileset. Aseprite's implicit Tileset creation remains an internal native step, never a public default or durable side effect.
_Avoid_: active Tileset, implicit Tileset 0, optional binding, orphan Tileset

**Tilemap Cel**:
A native Cel on a Tilemap Layer. Its Image uses Aseprite's tilemap pixel format, where each Image pixel is one Tile Cell rather than a Color Value. Its Canvas Pixel position combines with the Tileset Grid to locate those cells on the Sprite canvas.
_Avoid_: raster Cel, whole Tilemap Layer, implicitly created Frame content

**Tile Cell**:
One zero-based `tile_x`, `tile_y` coordinate in a Tilemap Cel's Image. It is a position in Tile Cell space, not a Canvas Pixel or a Tile Bitmap Pixel. The Tilemap Cel's effective Grid maps it to Canvas Pixel coverage.
_Avoid_: raster pixel, Tile Index, absolute canvas coordinate

**Tilemap Cel Grid**:
The effective native Grid for one Tilemap Cel: the Tileset Grid translated by the Cel's Canvas Pixel position. Inspection returns the Tileset Grid, Cel position, effective Grid, and computed Canvas coverage instead of treating Tile Cell and Canvas Pixel coordinates as interchangeable.
_Avoid_: global Sprite grid preference, Cel-local Tile Cell Rectangle, implicit origin

**Tile Placement**:
The native value stored at one Tile Cell in a Tilemap Cel's Image. It combines a Tile Index from the Layer's Tileset with independent X-flip, Y-flip, and diagonal-flip flags. Empty Tile Index 0 represents an empty cell; changing the Tileset's index order requires rewriting affected Placements to preserve their Tile meaning.
_Avoid_: Tile, Tile Image, packed public integer, Canvas Pixel

**Selection**:
An Aseprite-aligned pixel Mask represented in SPA's Published Language as an explicit serializable value in Canvas Pixel space. Aseprite's `Sprite.selection` is transient Document/editor-session state and is not a persistent Sprite File child. SPA materializes the value as a native Selection inside the Lua Operation Kernel when executing native mask behavior.
_Avoid_: persistent Sprite selection, object target selector, implicit active selection

**Selection Encoding**:
The canonical discriminated representation of a Selection: `empty`; `all` with its Canvas Rectangle; or `mask` with tight bounds and ordered binary pixel runs. A mask row has an absolute Canvas Pixel `y` and sorted, merged `{x, length}` runs. Inline values and Selection Mask Artifacts use the same schema.
_Avoid_: geometry-command history, arbitrary bitmap color data, unnormalized overlapping runs

**Selection Mask Artifact**:
A JSON Artifact with role `selection-mask` whose content is the canonical Selection Encoding. It carries large Selections without changing their semantics. A PNG rendering can be a separate Preview Artifact but is not an authoritative or reversible Selection.
_Avoid_: PNG mask authority, persisted Sprite selection, distinct file-only mask model

**Linked Cel**:
An Aseprite Cel that shares native Cel data, including its Image, with one or more other Cels. Raster changes to the shared Image affect the whole linked set; making one Cel independent is the separate `cel unlink` behavior.
_Avoid_: copied Cel, duplicate Frame, implicit paint policy

**Layer UUID**:
The native UUID exposed by Aseprite as `Layer.uuid`. It is a Persistent Identity only when the owning Sprite has `useLayerUuids` enabled, so Aseprite writes it to the Sprite File and restores it on reopen. A UUID generated in a process while that option is disabled is not a cross-Operation address.
_Avoid_: runtime Layer ID, universally persistent Layer identity, SPA Layer ID

**Layer Stack Path**:
An exact current-structure address expressed as the sequence of one-based native `Layer.stackIndex` values from the Sprite root through any parent groups to a Layer. Inspection returns it so a later Operation can address nested or duplicate-named Layers. Reorder or reparent operations can change it, so it is not a Persistent Identity.
_Avoid_: Layer UUID, name path, generic Locator, stable Layer identity

**Frame**:
One position in an Aseprite Sprite's animation timeline, with its own duration and one possible Cel intersection per Cel-bearing Layer.
_Avoid_: Cel, exported image, time instant

**Frame Number**:
The public one-based ordinal of a Frame, matching the number shown by Aseprite and exposed by Lua as `Frame.frameNumber`. Requests and results use the field name `frame_number`; zero-based storage positions and native CLI offsets remain private adapter or Kernel details.
_Avoid_: frame index, zero-based frame number, ambiguous `index`

**Frame Range**:
An inclusive interval whose endpoints are Frame Numbers. Both endpoints use the same one-based public convention; any conversion required by a native Aseprite CLI option occurs behind the SPA contract.
_Avoid_: half-open frame range, zero-based CLI range, implicit endpoint convention

**Frame Duration**:
The persisted display time of one Frame, represented publicly as integer `duration_ms` from 1 through 65535 milliseconds. Aseprite's Lua API projects the value as floating-point seconds, but that conversion is private to the Lua Operation Kernel and does not define another public duration unit.
_Avoid_: `duration_seconds`, unqualified duration, canonical frames-per-second

**Tag**:
The native named Aseprite animation range over inclusive Frame Numbers, with an Animation Direction, `repeats`, display color, and user data.
_Avoid_: exported clip, engine animation, Frame collection

**Animation Direction**:
The native Tag traversal direction represented publicly as `forward`, `reverse`, `ping-pong`, or `ping-pong-reverse` in `animation_direction`.
_Avoid_: boolean reverse, inferred endpoint sequence, export loop mode

**Tag Repeats**:
The persisted native `repeats` integer from 0 through 65535. Zero means unspecified, not universally infinite: Aseprite can interpret it differently in editor playback and export contexts.
_Avoid_: loop count, zero means infinite, export play count

**Tag Index**:
The current one-based position of a Tag in `Sprite.tags`, exposed as `tag_index`. Aseprite orders Tags by Frame Range and can reorder them when a range changes, so a Tag Index is an exact current-snapshot address rather than a Persistent Identity.
_Avoid_: Tag ID, stable Tag index, zero-based tag position

### SPA automation

**Operation**:
A channel-neutral SPA capability with one public request, result, and failure contract. The CLI, MCP, and an Operation Plan can invoke or project the same Operation.
_Avoid_: Command, tool, handler

**Operation Descriptor**:
The single public registration and contract-projection authority for one Operation. It binds the Operation's request, result, and failure schemas to its Execution Kind, Operation Determinism, other execution metadata, and packaged Lua handler. CLI Commands, MCP Tools, and the Surface Manifest are projections of Operation Descriptors rather than independently registered surfaces. The descriptor does not implement the Operation's Aseprite behavior.
_Avoid_: Command Descriptor, command registry, tool registry, Lua handler registry

**Published Language**:
The versioned public request, result, failure, Operation metadata, Artifact, and Surface Manifest schemas exposed consistently through SPA access channels. Human text and transport-specific envelopes are projections rather than independent contracts.
_Avoid_: Kernel Protocol, CLI prose, MCP text block

**Surface Manifest**:
The aggregate machine-readable projection of all dispatchable Operation Descriptors. It describes the installed SPA operation surface for discovery and MCP generation; it does not describe produced files.
_Avoid_: Artifact Manifest, command registry, help-text index

**Application Layer**:
The Python layer that coordinates SPA use cases around the Published Language and ports. It validates public requests, selects applicable packaged Kernel capabilities, constructs their private execution order and composition, invokes Aseprite, and manages staging, result, and Artifact lifecycles. It does not implement or replace Core Operation Semantics; native steps that share live Sprite state execute through the Lua Operation Kernel in the same Aseprite process.
_Avoid_: domain algorithm implementation, public workflow engine, passive transport wrapper

**Lua Operation Kernel**:
The versioned, packaged, Aseprite-resident implementation that is the sole authority for the core behavior of ordinary Operations. Its fixed handlers create, edit, observe, validate, convert, or export through Aseprite's native model and API, and the same handler serves standalone and Plan execution.
_Avoid_: generated script, public schema registry, disposable handler

**Core Operation Semantics**:
The authoritative meaning of what an ordinary Operation does to or observes from Aseprite objects. Core Operation Semantics live in one Lua Operation Kernel handler and are not reimplemented in Python entrypoints, adapters, or Plan code.
_Avoid_: public contract shape, CLI projection, duplicated Python behavior

**Temporary Operation Script**:
Lua source assembled or generated at runtime by SPA to implement an ordinary Operation. SPA prohibits Temporary Operation Scripts; temporary request, response, staging, and diagnostic files carry data rather than executable operation behavior.
_Avoid_: packaged Lua handler, caller-supplied raw script, temporary data file

**Caller Script**:
Lua source explicitly supplied by the caller to the unrestricted `script run` Operation, either as an existing file or as exact stdin bytes that SPA materializes because Aseprite requires a filename. A Caller Script is not a Lua Operation Kernel handler and SPA does not synthesize or inject behavior into it.
_Avoid_: Temporary Operation Script, ordinary Operation, packaged handler

**Kernel Protocol**:
The private, versioned request and response exchange between the Python Aseprite adapter and the Lua Operation Kernel. It carries data and execution facts for the installed SPA version and is translated into the Published Language rather than exposed as a second public API.
_Avoid_: Published Language, generic serialization framework, stdout prose

**Kernel Response**:
The explicit success or failure record written by the Lua Operation Kernel from facts it constructs after executing against Aseprite. A zero Aseprite process exit without a valid Kernel Response is not Operation success.
_Avoid_: public result, process exit code, echoed request document

**Color Value**:
The public discriminated value used where an Operation accepts or reports color or native pixel color: `rgba` with `red`, `green`, `blue`, and `alpha`; `grayscale` with `gray` and `alpha`; or `palette-index` with `palette_index`. Components are integers from 0 through 255, while a Palette Index must also exist in the applicable Palette. A packed Aseprite pixel integer is never a public Color Value.
_Avoid_: untagged color tuple, packed pixel integer, treating Palette Index as RGBA

**Image Resize Transform**:
The shared Raster Authoring transform that produces an exact positive `width/height` Image in the source Pixel Format using one explicitly selected Aseprite method: `nearest-neighbor`, `bilinear`, or `rotsprite`. It changes the Image buffer but has no Cel placement or pivot semantics. `image resize` and Tileset Resize `scale` use this same Lua Kernel authority.
_Avoid_: zero-size clamp, unknown-method fallback, Cel movement, Tileset-specific interpolation

**Indexed Resize Palette Basis**:
The required `palette_frame_number` for `bilinear` Image Resize Transform on an Indexed Image. It resolves one Effective Palette and Transparent Color Index used to convert indexes to RGBA, interpolate, and map results back through Aseprite's RGB Map without dithering. Nearest-neighbor and rotsprite operate on stored indexes and reject this irrelevant input.
_Avoid_: active Palette, first Palette, hidden nearest fallback, implicit dithering

**Image Resize Cel Position Policy**:
The required placement behavior composed by `image resize` with Image Resize Transform for ordinary transparent Image Layer Cels. `keep` preserves every affected Cel position. `pivot` keeps an explicit old-Image Pixel anchor as stable as integer Canvas placement permits by computing one rational position delta, applying a declared Pivot Rounding, and moving every Cel sharing the Image by the same integer delta.
_Avoid_: implicit top-left, hidden native truncation, per-linked-Cel divergence, Reference bounds resize

**Pivot Rounding**:
The required conversion of an Image Resize `pivot` position delta from a rational value to Canvas Pixels: `toward-zero`, `floor`, `ceil`, or `nearest-away-from-zero`. The same rule applies independently to X and Y, and the exact rational and resulting integer delta are reported.
_Avoid_: language default rounding, omitted rounding, silent fractional position

**Image Crop**:
The Image-buffer Operation that replaces an ordinary transparent Cel Image with one exact non-empty, fully contained half-open Rectangle from the source Image Pixel space. The Rectangle's origin becomes `(0,0)` in the result. Out-of-bounds padding belongs to Image Canvas, not Crop.
_Avoid_: Sprite Crop, Selection bounds, implicit clipping, canvas expansion

**Image Crop Cel Position Policy**:
The required placement behavior of Image Crop. `preserve_canvas_pixels` moves every Cel sharing the Image by the crop Rectangle's `x/y`, so retained pixels keep their Canvas locations. `keep_cel_position` leaves every Cel position unchanged and moves the retained region to the Cel's existing origin.
_Avoid_: hidden position shift, per-linked-Cel policy, crop Rectangle in Canvas Pixel space

**Image Canvas Transform**:
The shared Raster Authoring transform that creates an exact positive-size Image in the source Pixel Format, fills it with an explicit compatible Color Value, and copies source pixels 1:1 after placing the source origin at integer `offset_x/offset_y` in target Image Pixel space. Source pixels outside the target are discarded and uncovered target pixels retain the fill, including when no source pixel intersects the target. `image canvas-resize` and Tileset Resize `canvas` use this same Lua Kernel authority.
_Avoid_: Sprite Canvas Size, scaling, implicit fill, implicit centering, overlap guard

**Image Canvas Cel Position Policy**:
The required placement behavior composed by `image canvas-resize` with Image Canvas Transform. `keep_cel_position` preserves every affected Cel position, so copied source pixels move on the Sprite Canvas by the transform offset. `preserve_source_canvas` subtracts that offset from every Cel sharing the Image, preserving the Canvas coordinates of every copied source pixel.
_Avoid_: hidden Cel movement, per-linked-Cel divergence, mixing buffer offset with Canvas coordinates

**Image Flip**:
The whole-Image mirror Operation backed by Aseprite's native `Image:flip`. Its required axis is `horizontal`, which mirrors left and right, or `vertical`, which mirrors top and bottom. It preserves Image dimensions, Cel positions, Background invariants, Reference bounds, and native Image sharing, and it does not implicitly apply the current Selection.
_Avoid_: omitted-axis default, Selection flip, Tilemap cell reversal, custom pixel-mirror algorithm

**Image Quarter-turn Transform**:
The shared Raster Authoring transform that rotates stored Image Pixel values by the explicit Aseprite-aligned angle `90`, `-90`, or `180` using exact integer coordinate mapping. Positive `90` is clockwise. It preserves Pixel Format and stored values, swaps dimensions for `90/-90`, and has no Cel placement or Selection semantics. Aseprite 1.3.18.5 has no native Lua `Image:rotate`; the fixed Lua Kernel is the sole implementation authority.
_Avoid_: arbitrary angle, interpolation, angle normalization, `app.command.Rotate`, Python pixel loop

**Image Rotate Cel Position Policy**:
The required placement behavior composed by `image rotate` with Image Quarter-turn Transform for ordinary transparent Image Layer Cels. `keep` preserves every affected Cel position. `pivot` preserves an integer Point from old Image Pixel space, including an out-of-bounds Point, by subtracting its exact rotated coordinate from its original coordinate and applying that integer delta to every Cel sharing the Image.
_Avoid_: implicit center, fractional rounding, per-linked-Cel pivot, Reference bounds rotation

**Pixel Region Snapshot**:
The complete canonical Raster value for one positive half-open Rectangle in Image Pixel space. It declares the Aseprite Color Mode and contains exactly one ordered run-length row per pixel row; positive-length adjacent runs with the same compatible Color Value are merged and each row covers the Rectangle width exactly. The value has no omitted-pixel default. Inline JSON and JSON Artifact forms use the same schema.
_Avoid_: sparse default, packed pixel integer, RGBA expansion of Indexed pixels, alternate Artifact encoding

**Pixel Patch**:
The canonical sparse Raster mutation value for one positive half-open Rectangle in Image Pixel space. Its absolute `x/y` runs are ordered, non-overlapping, positive-length, contained by that Rectangle, and merged when adjacent values are equal. Listed pixels receive exact compatible stored Color Values; omitted pixels remain unchanged. An empty run list is an explicit no-op.
_Avoid_: complete Snapshot, implicit transparent fill, blend operation, unordered or overlapping writes

**Paint Composite**:
The Raster Authoring Operation that places a Pixel Region Snapshot at an explicit target Image Pixel position and composites it through required Aseprite `opacity` and supported BlendMode semantics. Bounds clipping and Selection Application reuse Paint rules. Source and target Color Modes match; Indexed composition declares the target Frame's Effective Palette basis and remains a reported Capability Gap until native Palette-correct execution is proven.
_Avoid_: Pixel Patch replacement, implicit Normal, clamped opacity, Palette 0 fallback, cross-mode coercion

**Composite Palette Basis**:
The required `palette_frame_number` for Indexed Paint Composite. It must resolve to the addressed target Cel Frame's Effective Palette and is the declared Palette used to interpret source/destination indexes and quantize the result. It never means first Palette or active editor Palette.
_Avoid_: Palette 0, active Palette, omitted basis, different target Frame

**Native Tool Invocation**:
The private Lua Kernel mechanism that translates one typed Paint primitive into a fully specified Aseprite `app.useTool` call against an explicit Cel, Layer, and Frame. It supplies every result-affecting option owned by that primitive, maps Image Pixel geometry to native Canvas coordinates, enforces declared bounds and Selection behavior, and restores invocation-local editor/tool state. It is not a public generic command or persistent session facility.
_Avoid_: public `use-tool`, active-tool default, GraphicsContext substitution, Python rasterizer, general state manager

**Standard Paint Brush**:
The typed Aseprite Brush used by Paint primitives when the footprint is `circle`, `square`, or `line`. It has a positive integer size; Circle has fixed angle 0, while Square and Line require an integer angle from -180 through 180. A Line Brush is a footprint and is distinct from the Line tool. Image Brush has separate mask, center, pattern, and color-replacement semantics.
_Avoid_: active Brush, non-positive-size clamp, Line tool alias, implicit Image Brush

**Paint Line**:
The Paint Operation that invokes Aseprite's native Line tool for exactly two Image Pixel Points through a Standard Paint Brush, Color Value, opacity, and supported Ink. Equal endpoints form a single-point stroke. Its affected region is the native Brush footprint, not merely the endpoint bounds.
_Avoid_: point-list freehand stroke, custom line rasterizer, endpoint-only bounds, hidden Shade state

**Paint Shape**:
The shared contract used by `paint rectangle` and `paint ellipse`. A positive half-open Image Pixel Rectangle defines the shape bounds and required `outline` or `filled` style selects the corresponding native Aseprite tool. Standard Paint Brush, Color Value, opacity, Ink, bounds/clipping, and Selection semantics match other native Paint primitives; degenerate one-pixel dimensions retain native shape behavior.
_Avoid_: GraphicsContext shape, implicit fill preference, Line substitution, keyboard modifier state

**Paint Fill**:
The Paint Operation that invokes Aseprite's native Paint Bucket from one Image Pixel seed. It explicitly supplies Color Value, opacity, Ink, tolerance, contiguous mode, Pixel Connectivity when applicable, Refer To, and Stop at Grid behavior. `active-layer` means the addressed target Layer; `all-layers` matches against the native visible composite for the addressed Frame while still writing only the target Cel.
_Avoid_: hidden Paint Bucket preference, GUI-grid visibility, Brush input, ignored connectivity, custom flood-fill algorithm

**Paint Pencil**:
The Paint Operation that sends one non-empty ordered Image Pixel Point sequence through Aseprite's native Pencil tool as one press/move/release gesture. It explicitly selects Standard Paint Brush, Color Value, opacity, Ink, and the native Regular, Pixel-perfect, or Dots Freehand Algorithm. Input Points are not deduplicated, simplified, interpolated, or reordered by SPA.
_Avoid_: generic stroke renderer, Line tool, normalized path, simulated Paint Dynamics, Spray or Eraser alias

**Paint Dynamics**:
Aseprite's pressure-, velocity-, and sensor-driven changes to Brush size, angle, gradient, and related Pencil behavior. Aseprite 1.3.18.5 does not expose complete Dynamics inputs to headless `app.useTool`, so SPA reports this intended functional capability as a typed Capability Gap until native-equivalent explicit execution is proven.
_Avoid_: GUI context inheritance, fixed-zero pressure presented as Dynamics, Python simulation, silent omission

**Paint Eraser**:
The Paint Operation that sends an ordered freehand gesture through Aseprite's native Eraser tool. Its explicit `erase` behavior uses native Eraser Ink; `replace-foreground-with-background` uses the Eraser tool's native alternate Ink. Transparent Layer erasure follows alpha or Transparent Color Index semantics, while Background erasure requires an explicit background Color Value.
_Avoid_: transparent Pencil color, public mouse button, generic Ink, implicit background color, custom erase algorithm

**Paint Spray**:
The intended Paint Operation that sends one ordered freehand gesture through Aseprite's native Spray tool with Standard Paint Brush, Color Value, opacity, Ink, Spray Width, and Spray Speed. The native time-seeded distribution makes it `native-stochastic`; SPA observes the actual result and does not add a seed or reimplement Spray. On Aseprite 1.3.18.5 it remains a reported Capability Gap until a fixed-Kernel native preference-priming slice proves explicit width and speed in headless execution.
_Avoid_: deterministic pixel promise, Freehand Algorithm, fixed-default partial command, SPA random generator, Python spray

**Paint Gradient**:
The intended deterministic Paint Operation that sends ordered `from` and `to` Image Pixel Points through Aseprite's native Gradient tool. It uses explicit foreground/background Color Values, opacity, Linear or Radial Gradient Type, Dithering Matrix, and Paint Fill matching controls; `from` is also the Flood Fill seed. Aseprite 1.3.18.5 remains a reported Capability Gap until real headless execution can supply GUI-owned Gradient Type and Dithering Matrix state.
_Avoid_: unordered axis, Brush, generic Ink, implicit Context Bar, Paint Composite substitute, custom gradient renderer

**Dithering Algorithm**:
The native Aseprite algorithm applied only when Change Color Mode converts an RGB Sprite to Indexed. The Published Language values are `none`, `ordered`, `old`, and `error-diffusion`; each determines whether a Dithering Matrix or Dithering Factor is applicable.
_Avoid_: Grayscale conversion option, implicit preference, unknown-value fallback, custom quantizer

**Dithering Matrix**:
The native Aseprite matrix used by Ordered or Old Dithering and by Paint Gradient to define a spatial threshold pattern. For Change Color Mode it is either one uniquely resolved installed matrix ID or a matrix file path; omitting it for Ordered or Old Dithering uses Aseprite's native Bayer 8-by-8 default. Matrix identity, source, resolution, and dimensions are reported explicitly.
_Avoid_: Dithering Algorithm, implicit active matrix, ambiguous ID, unknown-name fallback, SPA-generated matrix

**Dithering Factor**:
The native `0..1` factor controlling Floyd-Steinberg error propagation for the `error-diffusion` Dithering Algorithm. It is required for that algorithm and inapplicable to `none`, `ordered`, and `old`.
_Avoid_: Dithering Matrix strength, UI percentage without conversion, generic opacity, SPA diffusion control

**Paint Curve**:
The intended deterministic Paint Operation corresponding to Aseprite's native Curve tool, Four Points Controller, and Bézier Intertwiner. Its start, first control Point, second control Point, and end retain their exact ordered roles alongside Standard Paint Brush, Color Value, opacity, and accepted Ink. Aseprite 1.3.18.5 is a proven Controller Capability Gap: one scripted `app.useTool` gesture cannot complete the multi-phase controller, and a real probe produced no pixels while returning success. Paint Curve is absent from that runtime's Surface Manifest until a supported native route makes all four roles observable.
_Avoid_: generic Path, arbitrary segment list, ignored control Points, Line degradation, SPA Bézier rasterizer

**Paint Polygon**:
The intended deterministic Paint Operation corresponding to Aseprite's native Polygon tool and Point-by-Point Controller. Ordered Image Pixel vertices, Standard Paint Brush, Color Value, opacity, and accepted Ink retain native always-filled closure. Aseprite 1.3.18.5 is a proven Controller Capability Gap: one scripted `app.useTool` gesture loses intermediate vertices, and repeating the first vertex as a synthetic completion can fill the whole canvas. Paint Polygon is absent from that runtime's Surface Manifest until a supported native route makes every vertex and completion observable.
_Avoid_: generic Path, Contour alias, repeated-first-vertex completion, repeated Tool invocation, SPA scanline fill

**Paint Contour**:
The deterministic Paint Operation corresponding to Aseprite's native Contour tool: one non-empty ordered Image Pixel Point sequence is preserved as one Freehand press/move/release gesture, and the native tool closes and fills the sampled contour. It requires Standard Paint Brush, Color Value, opacity, accepted Ink, and the operation-specific Freehand Algorithm `regular` or `pixel-perfect`. It has no caller-selectable closure or fill mode. Its delivery gate is independent of Curve and Polygon because its controller is directly expressible by `app.useTool`.
_Avoid_: Polygon alias, outline or open mode, `dots`, Paint Dynamics, Point normalization, SPA polygon renderer

**Paint Blur**:
The deterministic Paint Operation that sends one non-empty ordered Image Pixel Point sequence through Aseprite's native Blur tool as a Freehand gesture. It uses Standard Paint Brush, opacity, the operation-specific Regular or Pixel-perfect Freehand Algorithm, and explicit Tiled Mode. Native Blur Ink applies its 3-by-3 neighboring-pixel behavior; Color Value and caller-selected Ink are not inputs.
_Avoid_: Filter blur, color input, generic Ink, `dots`, hidden Tiled Mode, custom convolution

**Paint Jumble**:
The intended `native-stochastic` Paint Operation corresponding to Aseprite's native Jumble tool, Freehand Controller, Brush, opacity, Tiled Mode, random neighboring-pixel choice, and pointer velocity/direction. Aseprite 1.3.18.5 is a Capability Gap because `app.useTool` fixes every Pointer velocity to zero. SPA does not publish a zero-velocity subset or infer velocity from Point spacing.
_Avoid_: deterministic result, fixed-zero partial command, derived velocity, Blur or Filter alias, custom random displacement

**Tiled Mode**:
Aseprite's explicit neighboring-pixel wrap behavior: `none`, `x`, `y`, or `both`. Paint Blur and the intended Paint Jumble use it at Image edges. When the native invocation reads document state rather than a direct argument, the fixed Lua Kernel sets and restores that state and reports the effective value.
_Avoid_: Tilemap Mode, hidden document preference, implicit edge clamp, global execution setting

**Filter Operation**:
A Raster Authoring Operation corresponding to one Aseprite native Filter command, such as Brightness/Contrast, Hue/Saturation, Color Curve, Replace Color, Invert Color, Outline, Convolution Matrix, or Despeckle. Each Filter owns its explicit target, channel, Selection, Frame/Cel range, tiled-mode, parameter, and result contract. `filter` is a CLI navigation group and not a new bounded context, generic algorithm, or plug-in protocol. Aseprite's Freehand Blur and Jumble tools remain Paint Operations because they use a Brush gesture rather than the Filter command lifecycle.
_Avoid_: universal Effect, Filter DSL, arbitrary plug-in, Paint Blur/Jumble reclassification, Adjustments/FX bounded contexts

**Filter Cels Target**:
The Filter-specific explicit choice between Aseprite's native `selected` and `all` Cel scopes. `selected` carries non-empty, exactly resolved Layer addresses and unique one-based Frame Numbers and targets existing Cels in their Cartesian product; empty intersections are reported and not created. `all` means every existing Cel on a Layer that satisfies Aseprite's native pixel-editability rule and reports excluded Layers. The value is required, never inherited from the active Cel or timeline range, and remains distinct from pixel Selection Application.
_Avoid_: universal Selector, ambient timeline selection, active-Cel fallback, implicit all, empty-Cel creation, hidden non-editable skip

**Filter Channels**:
The Filter-specific typed value that replaces Aseprite's internal channel bitmask. `components` contains a non-empty unique set of Color-Mode-compatible names—RGB or Indexed component interpretation uses red, green, blue, and alpha; Grayscale uses gray and alpha—while the exclusive `index` form denotes stored Palette Index processing for an Indexed Sprite. Each Filter Descriptor accepts only channels its native implementation actually affects; channels are explicit, and Alpha is invalid when any resolved target is a Background Cel.
_Avoid_: raw bitmask, implicit Filter default, empty set, Index/component mixture, accepted no-op channel, Background Alpha stripping

**Filter Application**:
The explicit destination semantics of a native Filter whose Aseprite behavior can branch between pixels and Palette state. Brightness/Contrast and Hue/Saturation distinguish `pixels`, Indexed `indexed-palette-entries`, and RGB `rgb-palette-colors`: the first mutates targeted Images, the second mutates one exact Palette Change while preserving stored indexes, and the third preserves Aseprite's combined selected-Entry plus exact-matching-pixel behavior. Other Filters omit this value when their application meaning is fixed.
_Avoid_: ambient pixel Selection branch, ambient Palette Picks, generic field on every Filter, conflating channels with entries, Lua/Python color math

**Brightness/Contrast Filter**:
The deterministic native Filter Operation that requires explicit integer Brightness and Contrast percentages in `-100..100`. RGB and Indexed component processing accepts non-empty red/green/blue subsets; Grayscale accepts gray. Alpha, Index, Tiled Mode, and custom tonal formulas are not part of the Operation. It uses the applicable Filter Application while Aseprite remains authoritative for mapping, clamping, quantization, Palette behavior, and rounding.
_Avoid_: fractional or extrapolated percentage, Alpha/Index no-op channel, gamma, Color Curve alias, reimplemented transfer function

**Hue/Saturation Filter**:
The deterministic native Filter Operation with explicit `hsl-multiply`, `hsl-add`, `hsv-multiply`, or `hsv-add` color adjustment, a distinct multiplicative `grayscale` Lightness adjustment, and conditional Alpha adjustment. HSL uses Hue/Saturation/Lightness, HSV uses Hue/Saturation/Value, and every percentage input is an integer in its native editor range. Only fields capable of affecting the selected Filter Channels are present; Index is unsupported.
_Avoid_: numeric mode enum, unknown-mode fallback, HSV lightness, Grayscale hue/saturation, Index channel, custom color conversion

**Color Curve Filter**:
The deterministic native pixel Filter whose required `points` are 1..256 strictly input-ordered integer `{input, output}` pairs in the 8-bit `0..255` domain. One Point is constant; native Linear interpolation and endpoint extension apply otherwise. RGB/Grayscale component Channels and Indexed component-or-Index interpretation are explicit, with a declared Effective Palette basis for Indexed execution. It never mutates Palette Entries.
_Avoid_: unordered or duplicate input, empty curve, required identity endpoints, Spline, formula, separate lookup table, hidden active Palette

**Replace Color Filter**:
The deterministic native pixel Filter that requires compatible `from` and `to` Color Values plus one integer Tolerance in `0..255`. Component mode matches when every selected component is independently within Tolerance and preserves unselected components. Indexed mode uses explicit valid Palette Index source/destination values for either stored-Index comparison or Effective-Palette component matching and RGB Map replacement. Results distinguish matched from actually changed pixels.
_Avoid_: implicit foreground/background colors, Indexed best-fit input, aggregate color distance, per-channel tolerance, equality-implies-no-op, custom quantizer

**Invert Color Filter**:
The deterministic native pixel Filter that complements selected RGB, Grayscale, Indexed component, or stored Index values. Indexed execution declares an Effective Palette basis. Because native Index inversion produces `255-index` without Palette-size clamping, preflight requires every participating source and inverted Index to remain valid in that Palette or fails without mutation. Indexed component quantization prevents a general two-pass restoration promise.
_Avoid_: implicit channels, invalid Palette Index, automatic Palette growth, Index clamp, component fallback, universal involution claim

**Outline Filter**:
The deterministic native pixel Filter that writes an explicit Outline Color where an `inside` or `outside` candidate matches an explicit Background Color and one typed 3-by-3 Outline Matrix. Presets preserve None, Circle, Square, Horizontal, and Vertical; a custom Matrix names the eight effective neighboring positions and never exposes the inert center or raw bit mask. Tiled Mode governs edge wrapping. RGB and Grayscale use component Channels, while Aseprite 1.3.18.5 supports Indexed stored-Index execution and reports its broken Indexed component path as a version-specific Capability Gap.
_Avoid_: Paint Shape outline, implicit editor colors, raw Matrix integer, effective center cell, thickness or radius, custom renderer, Indexed component fallback

**Convolution Matrix Resource**:
An Aseprite stock Resource addressed by its exact name and containing the native Convolution Matrix dimensions, center, coefficients, divisor, bias, and declared default Channels. SPA reports discovered names, source locations, duplicate-name facts, and declared defaults so an agent can resolve one definition explicitly; the Resource does not create an inline Matrix or Filter-extension language.
_Avoid_: arbitrary convolution request, implicit last-selected Matrix, resource name without resolution, generic Filter plug-in

**Convolution Matrix Filter**:
The intended deterministic native pixel Filter that applies one uniquely resolved Convolution Matrix Resource with explicit Filter Channels, Tiled Mode, Filter Cels Target, and Selection. Aseprite 1.3.18.5 is a Capability Gap because its headless command ignores both the supplied Channels and the Resource's default target and treats a missing Resource as a successful no-op. SPA publishes no fixed-all-component subset or duplicate renderer.
_Avoid_: implicit all Channels, missing-resource success, inline Matrix, Lua/Python convolution, fixed-default partial command

**Despeckle Filter**:
The deterministic native Aseprite Median Filter over an explicit rectangular neighboring-pixel window. Width and height are each `1..100`; even sample counts use Aseprite's upper median, and `1x1` is a valid no-op. RGB and Grayscale use component Channels. Indexed supports stored-Index medians and Effective-Palette component medians, except that Aseprite 1.3.18.5 reports a combination-level Capability Gap when component Channels omit Green because the native path corrupts the unselected Green value.
_Avoid_: Median command alias, odd-size restriction, percentile filter, implicit dimensions, Indexed Green repair, custom median implementation

**Coordinate Space**:
The domain frame in which a Point or Rectangle is interpreted, such as Canvas Pixel, Image Pixel, Tile Cell, or Tile Bitmap Pixel. An Operation declares its space through typed fields or schema metadata rather than relying on generic `x` and `y` alone.
_Avoid_: universal geometry, inferred space, interchangeable pixel and tile coordinates

**Clipping Behavior**:
An Operation's explicit rule for a requested Rectangle that crosses its target bounds. Raster writes reject out-of-bounds regions unless that Operation declares a caller-selectable `clip` behavior; a clipped success reports the Rectangle actually applied.
_Avoid_: silent clipping, global geometry policy, treating an off-canvas Cel position as a raster write

**Selection Application**:
The explicit use of a Selection request value to constrain an Image, Paint, copy, move, erase, transform, or other owning Operation. An absent Selection means no selection restriction, an explicit empty Selection contains no pixels, and an explicit all-canvas Selection contains every Canvas Pixel; these states are never conflated.
_Avoid_: hidden `Sprite.selection`, Plan-current Selection, interpreting empty as all

**Operation Result**:
The schema-valid public success value returned when an Operation completed and its required facts and Artifacts were verified. It never contains an alternate failure branch.
_Avoid_: Kernel Response, success envelope, prose receipt

**Failure Envelope**:
The schema-valid public failure value returned with a non-zero CLI exit and relayed losslessly through other access channels. It contains a stable Failure Code, a broad Failure Category, a message, and code-specific typed details or diagnostics when they help the caller respond.
_Avoid_: Operation Result, error string, Kernel failure response

**Failure Code**:
A stable machine-readable identifier for one recoverable or actionable failure meaning. Agents branch on the code rather than parsing message or diagnostic text.
_Avoid_: exit code, exception class, message

**Failure Category**:
A broad stable classification used for process exit behavior and coarse caller policy. It does not replace the more specific Failure Code.
_Avoid_: Failure Code, Aseprite exit code

**Failure Details**:
A code-specific typed object containing facts an agent needs to respond to that Failure Code. SPA does not use an arbitrary dictionary or one sparse object containing every possible failure field.
_Avoid_: diagnostics, generic context map, universal evidence model

**Diagnostic**:
Human-oriented or captured process information that explains an outcome but is not a stable machine-branching contract.
_Avoid_: Failure Code, Failure Details, Validation Finding

**Execution Kind**:
The side-effect and trust classification of an Operation: `read`, `mutation`, `export`, or `script-run`. Validation is a read purpose, not another Execution Kind.
_Avoid_: command group, capability category

**Operation Determinism**:
The declared result-repeatability class in an Operation Descriptor and Operation Result. `deterministic` means the same validated request, source state, supported runtime, and declared environment facts produce the same governed domain result. `native-stochastic` means Aseprite intentionally uses native randomness that SPA cannot seed; the request remains explicit and the actual result remains observed and verified, but exact pixel replay is not promised.
_Avoid_: Execution Kind, best-effort flag, hidden randomness, universal byte-reproducibility claim

**CLI Command**:
The CLI syntax that invokes an Operation.
_Avoid_: Operation, Aseprite Command

**Command Group**:
A public navigation grouping of CLI Commands, normally named after an Aseprite object or cohesive Aseprite concept. It organizes discovery and help but does not by itself define a code-ownership boundary.
_Avoid_: bounded context, namespace, mandatory module

**Command Catalog**:
The human-maintained, incremental, non-binding map of candidate and established CLI capability territory. It records grouping rules, provisional command spellings, and semantic notes, while GitHub issues own commitment and delivery status and the installed Surface Manifest owns the shipped callable contract.
_Avoid_: command registry, schema, task tracker, release commitment

**Meta Command**:
A top-level CLI Command about SPA or its installed Aseprite runtime rather than an Aseprite domain object, such as `spa info`, `spa version`, `spa schema`, or `spa skill`. Meta Commands are exempt from domain Command Groups and cannot be Plan Steps.
_Avoid_: Command Group, Operation category, domain command

**MCP Tool**:
The MCP projection of an Operation.
_Avoid_: Operation, CLI Command

**Plan Step**:
One invocation of a Sprite-bound read or mutation Operation inside an Operation Plan. Export, script-run, and meta Operations cannot be Plan Steps.
_Avoid_: Command, workflow step

**Aseprite Command**:
A named native Aseprite editor action exposed through `app.command`.
_Avoid_: Operation, CLI Command, Lua handler

**Operation Plan**:
A bounded ordered set of Sprite-bound read and mutation Operations applied to one Sprite as one automation request. Read-only validation and declared postconditions can observe the same in-memory Sprite. A mutating plan commits at most one declared `.aseprite` target after successful validation; export, script-run, meta Operations, multiple Sprites, and project workflows remain outside the plan.
_Avoid_: Workflow, pipeline, asset recipe, cross-document transaction

**Validation**:
A read-only evaluation of Sprite or Artifact facts against declared rules. A completed Validation can report nonconformance without becoming an Operation execution failure, and it remains owned by the domain concept it checks rather than a top-level command group.
_Avoid_: Execution Kind, validation context, validation command group

**Validation Finding**:
A structured statement that an observed fact does not conform to a Validation rule. A Finding is data in a successful Validation result, not by itself an execution failure.
_Avoid_: exception, diagnostic, warning string

**Inspection Scope**:
The operation-specific set of sections, objects, Frame Ranges, Rectangles, or other domain bounds that an inspection request asks SPA to observe. An inspection result reports the normalized scope it actually evaluated and explicitly distinguishes optional sections that were not requested.
_Avoid_: universal query, hidden default selection, unbounded document dump

**Inspection Coverage**:
The domain-specific facts in a windowed or chunked inspection result that state which requested range, region, or page was returned and whether it completes the broader requested traversal. It is not a universal Observation Envelope or cross-domain cursor protocol.
_Avoid_: silent truncation, global pagination framework, generic evidence wrapper

**Complete Inspection**:
The guarantee that an inspection success contains all facts promised for its normalized Inspection Scope. Native absence is represented by an empty collection or a schema-defined `null`; a requested unsupported capability or exceeded Domain Bound fails instead of returning an unexplained partial result.
_Avoid_: best-effort inspection, warning-only omission, treating not requested as empty

**Postcondition**:
A declared assertion that must hold after a Plan Step or Operation Plan. An unmet Postcondition fails the plan and prevents its target from being committed.
_Avoid_: Validation Finding, process error

**Preflight**:
Validation of request shape and other statically decidable constraints before Aseprite execution starts. It checks the Operation surface, Plan Step eligibility, paths, declared limits, and cross-field rules, but does not claim to resolve objects inside a Sprite. A Preflight failure prevents execution.
_Avoid_: document target resolution, content validation, postcondition

**Step Precondition**:
A document-dependent assertion evaluated against the current in-memory Sprite immediately before its Plan Step. It resolves that Operation's target fields, enforces its target-count rules, and can refer to objects created by earlier steps. An unmet Step Precondition fails the plan before the guarded step mutates the Sprite.
_Avoid_: Preflight, Postcondition, eager plan validation

**Guard**:
A commit-protecting condition expressed as a Preflight rule, Step Precondition, or Postcondition. The phase determines which facts the Guard may observe and when failure occurs.
_Avoid_: Validation, generic check

**Persistent Identity**:
An identity proven to survive the required save, close, and reopen lifecycle. SPA uses an Aseprite-native persistent identity where one exists; it introduces an SPA Key only when a functional requirement needs persistence and Aseprite provides no suitable identity.
_Avoid_: runtime object ID, operation result fact, universal ID

**Layer UUID Policy**:
SPA-created Sprites enable Aseprite's native `useLayerUuids` option by default, with an explicit creation option to disable it. Operations on an existing Sprite preserve its current setting and never enable it as an implicit side effect of inspection or target resolution. Inspection reports whether the option is enabled, and only a persisted Layer UUID is valid for cross-Operation addressing.
_Avoid_: silently upgrading an existing Sprite, treating a generated runtime UUID as persistent, parallel SPA identity

**Layer Addressing**:
The Layer-specific target forms used by an Operation: a persisted `layer_uuid`, a current `layer_stack_path`, or a convenient `layer_name` where exactly one Layer in that Operation's documented scope has the name. A missing or ambiguous address fails explicitly. These forms do not establish a cross-domain Selector abstraction.
_Avoid_: implicit active Layer, first matching name, universal Selector, treating Layer Stack Path as identity

**Tag Addressing**:
The Tag-specific target forms used by an Operation: a current `tag_index`, or a `tag_name` that matches exactly one Tag. Missing and duplicate-name matches fail explicitly. Inspection and mutation results return the Tag's current index and complete persisted facts; no internal Aseprite object ID, synthetic UUID, or SPA Key is a Tag identity.
_Avoid_: first matching Tag name, persistent Tag index, Tag UUID, universal Selector

**Palette Addressing**:
Palette reads resolve an Effective Palette from `frame_number`; Palette entry mutations target an existing Palette Change by its exact `palette_frame_number`. Results expose the Palette Change and its inclusive effective Frame Range. Palette Index remains an entry position and no collection position, internal object ID, UUID, or generic Selector identifies a Palette.
_Avoid_: active Palette, Palette Index as object identity, hidden multi-Frame effect

**Slice Addressing**:
The Slice-specific target forms used by an Operation: a current `slice_index`, or a `slice_name` that matches exactly one Slice. Missing and duplicate-name matches fail explicitly. Inspection and mutation results return the Slice's current index, complete Slice properties, and every explicit Slice Key with its effective Frame Range; no internal object ID, synthetic UUID, SPA Key, or generic Selector identifies a Slice.
_Avoid_: first matching Slice name, persistent Slice Index, Slice UUID, universal Selector

**Single-Key Slice Mutation**:
The supported Aseprite 1.3.18.5 mutation of `bounds`, `center`, or `pivot` when a Slice has exactly one explicit Slice Key at Frame 1. SPA refuses this Operation for a multi-Key Slice or a Slice whose sole Key starts later, because the public Lua properties cannot target arbitrary Keys without changing timeline meaning.
_Avoid_: implicit first-Key edit, multi-Key overwrite, synthesized key lifecycle

**Tileset Addressing**:
The Tileset-specific target forms used by a direct Tileset Operation: current one-based `tileset_index`, or `tileset_name` when exactly one Tileset has that name. A Layer-scoped Operation can instead resolve the Tileset referenced by one Tilemap Layer through normal Layer Addressing. Missing and ambiguous targets fail; SPA adds no Tileset UUID or Tileset Key.
_Avoid_: zero-based native Tileset reference, first matching name, Base Index, universal Selector

**Tileset Removal**:
The lifecycle Operation that removes an exactly addressed Tileset after proving that no Tilemap Layer references it. A referenced target produces `TILESET_IN_USE` with the complete referencing Layer facts and no mutation. Explicit Layer-to-Tileset rebinding is a separate composable Operation; SPA never inherits Aseprite's implicit reassignment to Tileset 0.
_Avoid_: implicit Tileset 0 fallback, cascading Layer deletion, hidden rebind, general orphan collection

**Tilemap Layer Tileset Rebinding**:
The `layer set-tileset` Operation that changes one exactly addressed Tilemap Layer from its current Tileset to one exactly addressed target Tileset while translating every non-empty Placement by Tile Key. Its explicit mapping and Grid policies distinguish semantic Tile replacement from the Canvas coverage change caused by using a different Tileset Grid.
_Avoid_: raw `Layer.tileset` assignment, Tile Index preservation, implicit same-name mapping, hidden Grid change

**Tile Rebinding Map**:
The discriminated Placement translation used by Tilemap Layer Tileset Rebinding. `by_key` maps each used source Tile Key to an identical unique target Key; `explicit` completely maps each used source Tile Key to one uniquely resolved target Tile Key or Empty Tile. Empty Tile always remains Empty, and no mode maps by Tile Index; several source Keys can deliberately map to the same target Key.
_Avoid_: partial mapping, nearest-image matching, positional mapping, unkeyed source Tile

**Tileset Grid Policy**:
The required spatial intent of Tilemap Layer Tileset Rebinding. `require_equal` accepts only identical source and target Grids. `use_target` keeps Tile Cell coordinates and Cel positions unchanged, applies the target Grid without resampling, and reports the resulting effective Grids and Canvas coverage.
_Avoid_: automatic resampling, implicit target Grid, inferred coverage preservation

**Tileset Resize**:
The replacement-style lifecycle Operation that changes a Tileset's Grid by constructing a new Tileset, transforming and preserving its Tiles and Properties under declared policies, rebinding every referencing Tilemap Layer, and removing the old Tileset atomically. Aseprite has no writable Grid property on an existing Tileset; the result therefore reports old and replacement Tileset facts rather than claiming in-place identity.
_Avoid_: `tileset set grid`, raw Grid assignment, hidden Sprite resize, stable Tileset identity

**Tile Image Transform**:
The required Tile Bitmap policy of Tileset Resize. `scale` resizes every non-empty Tile through the shared Image Resize semantics. `canvas` applies the shared Image Canvas Transform in Tile Bitmap Pixel space, preserving source pixels 1:1, clipping outside pixels, and filling the remainder with an explicit compatible Color Value.
_Avoid_: implicit interpolation, Tile Cell resize, hidden crop anchor, transparent default fill

**Tileset Resize Cel Position Policy**:
The required policy for every Tilemap Cel referencing a resized Tileset. `keep_canvas_position` retains its Canvas Pixel position. `preserve_grid_position` requires exact alignment to the old Grid and converts the integral Grid coordinate to the new Grid without rounding. Both preserve Tile Cell dimensions and Placements and can change Canvas coverage.
_Avoid_: implicit Cel movement, rounded Grid coordinate, Tilemap resampling, Sprite canvas resize

**Tile Key**:
A caller-supplied, non-empty string persisted as `tile_key` in the documented, versioned `aigengame.spa` Tile properties namespace. It is unique among non-empty Tiles in one Tileset and preserves the Tile's agent-facing identity when native Tile Indexes move. SPA-created non-empty Tiles require one; existing unkeyed or duplicate-keyed Tiles remain inspectable and are never modified as a side effect of reading.
_Avoid_: Tile Index alias, generated UUID, global Tile identity, Empty Tile property

**Tile Addressing**:
Persistent Tile references and Tile Placements use a Tile Key within an exactly resolved Tileset. Results include both `tile_key` and the current native `tile_index`. A current Tile Index can be used to inspect a Tile or explicitly assign a missing Tile Key, but it is not used as a durable authoring reference. Duplicate Tile Keys fail key-based targeting as ambiguous and can be reported as Validation Findings.
_Avoid_: Base Index, raw packed tile value, implicit key assignment, globally unique Tile Key

**Tile Index Remap**:
The complete old-to-new Tile Index mapping applied to every Tile Placement in every Tilemap Layer and Cel that references one Tileset when Tile lifecycle changes its index order. Remapping preserves each Placement's X/Y/diagonal flags, is part of the same all-or-nothing Mutation as the lifecycle change, and is returned with complete affected Layer, Cel, and Tile Cell facts.
_Avoid_: array shift without placement rewrite, implicit replacement, best-effort cleanup

**Tile Removal Replacement**:
The explicit destination for Placements that use a Tile being removed: either the Empty Tile or another Tile Key in the same Tileset. It is required when the removed Tile is used; an unused Tile needs no replacement. SPA does not infer a visually similar Tile or silently clear cells.
_Avoid_: nearest-image match, automatic deduplication, missing replacement for a used Tile

**Tile Reorder**:
An agent-facing atomic Operation whose `tile_key_order` is a complete permutation of every non-empty Tile Key in one Tileset. Empty Tile remains at Tile Index 0 and Base Index remains unchanged. Each Tile's Image, color, data, Tile Key, and other Properties move together, while a complete Tile Index Remap preserves all Tile Placements and their flags.
_Avoid_: partial move, implicit sort, content-only swap, Base Index rewrite

**Tile Placement Value**:
The public discriminated value used to inspect or write one Tile Cell: `empty`, or `tile` with a Tile Key and explicit `flip_x`, `flip_y`, and `flip_diagonal` booleans. Mutation accepts only these forms. Inspection of a native Placement additionally reports its current Tile Index and can return `tile_key: null` for an existing unkeyed Tile without losing the Placement.
_Avoid_: packed tile integer, Base Index, bare Tile Index mutation, Color Value

**Tilemap Target**:
Exactly one Tilemap Layer resolved through Layer Addressing plus one one-based `frame_number`. `tilemap get`, `tilemap set`, `tilemap patch`, and `tilemap fill` require an existing Tilemap Cel at that intersection and interpret their Rectangle or Cell coordinates in Cel-local Tile Cell space; Cel creation remains a separate Operation that can be composed in an Operation Plan.
_Avoid_: active Layer or Frame, Canvas Pixel Rectangle, implicit Cel creation

**Tile Region Snapshot**:
The canonical complete value for one Tile Cell Rectangle. Empty Tile is the fixed default; `cells` contains every non-empty Placement in ascending `tile_y`, then `tile_x` order using absolute Cel-local coordinates. Omitted coordinates are explicitly Empty, while duplicate or out-of-Rectangle coordinates are invalid. Inspection can include `tile_key: null` and current Tile Index; mutation uses the same structure but requires keyed non-empty Placement Values.
_Avoid_: implicit unchanged cells, relative coordinates, dense unbounded grid, unordered overrides

**Tilemap Patch**:
A bounded list of unique absolute Cel-local Tile Cell coordinates and writable Placement Values. Only listed Cells change; all other Cells retain their current Placement. This is distinct from a Tile Region Snapshot replacement, where omitted Cells become Empty.
_Avoid_: partial Tile Region Snapshot, implicit Rectangle clearing, duplicate cell writes

**Palette Reorder**:
An agent-facing atomic Operation that reorders Palette Entries and applies the corresponding index permutation so applicable Indexed pixels continue to resolve to the same RGBA colors. Its explicit `palette-change` or `sprite` Palette Reorder Scope controls which Palette Changes and Images participate.
_Avoid_: entry recolor, reorder without pixel mapping, preference-driven remap

**Palette Reorder Scope**:
The discriminated `scope` of Palette Reorder. `palette-change` targets one exact Palette Change and its effective Frame Range, requires the Transparent Color Index to remain fixed, and refuses an Image shared outside that range. `sprite` applies one valid permutation to every Palette Change and every Indexed Image and can remap the global Transparent Color Index.
_Avoid_: generic mutation scope, silent scope expansion, automatic Cel unlink

**Cel Existence**:
The explicit distinction between an absent Cel and an existing Cel at a Layer/Frame intersection. `cel add` requires absence and never replaces existing content; Image and Paint mutations against a Sprite require an existing Cel/Image. Agents compose `cel add` with raster Operations in an Operation Plan when both behaviors are needed.
_Avoid_: editor auto-create preference, implicit `create_if_missing`, treating a transparent Image as no Cel

**Empty Frame Addition**:
The `frame add` behavior that inserts a Frame without copying an adjacent Frame. Transparent Layer intersections remain without Cels, while a Background Layer receives its required filled Cel. The request declares insertion position and duration and, when a Background Layer exists, its Background Color.
_Avoid_: duplicate Frame, inherit adjacent duration, native preference-derived background fill

**Frame Duplication**:
The `frame duplicate` behavior that inserts a copy of one source Frame, normally immediately after it, with an explicit `copy` or `link` Cel mode. Source duration is copied unless overridden; missing transparent-Layer Cels remain absent, and native Frame/Tag adjustments are reported.
_Avoid_: Empty Frame Addition, implicit `Layer.isContinuous`, partial-Layer Cel copy

**Frame Rate Input**:
An optional high-level Animation Operation convenience expressed as frames per second and deterministically quantized into Frame Durations. It is not a second stored timing authority; the result reports the actual `duration_ms` values produced.
_Avoid_: Frame Duration, implicit rounding, floating-point persisted timing

**Playback Context**:
The explicit interpretation used by an Operation that consumes a Tag, such as Aseprite Tag playback semantics or a caller-declared play count for an export. The result reports the actual expanded Frame Number sequence and output loop/timing facts without changing the Tag.
_Avoid_: universal interpretation of Tag Repeats, hidden export default, persisted loop count

**Cel Clear**:
An explicit mutation that preserves the Cel while replacing its Image content with the Layer-kind-appropriate empty value: transparent pixels for a transparent Layer or the declared Background Color for a Background Layer. It is distinct from `cel remove`.
_Avoid_: delete Cel, implicit absence, native `deleteCel` naming

**SPA Key**:
A narrowly scoped Persistent Identity stored in SPA's versioned custom-properties namespace when no Aseprite-native identity satisfies a proven functional requirement.
_Avoid_: replacement for an Aseprite UUID, global object ID

**Domain Bound**:
A constraint intrinsic to the meaning and usable result of an Operation, such as paint payload dimensions, a tilemap observation region, or the number of Plan Steps. Its domain module owns its units, defaults, validation, and tests.
_Avoid_: global quota, resource-budget dimension

**Execution Guard**:
An adapter-level bound on one Aseprite invocation, such as a timeout or captured-output cap, that keeps process execution observable and controllable. It is not a cross-Operation budget ledger or resource-governance API.
_Avoid_: quota system, policy engine, Domain Bound

**Source Sprite File**:
An existing `.aseprite` file opened as the input to a mutation. It remains distinct from the Target Sprite File even when an In-place Mutation intentionally uses the same host path.
_Avoid_: Sprite, input asset, implicit target

**Target Sprite File**:
The declared `.aseprite` file that a successful mutation commits. Creating a Sprite requires a Target Sprite File; editing requires either a distinct Target Sprite File or explicit In-place Mutation intent.
_Avoid_: staging file, export Artifact, inferred output

**In-place Mutation**:
Explicit caller intent to use the Source Sprite File as the Target Sprite File. Path equality without that intent is rejected and never treated as implicit overwrite.
_Avoid_: default edit, save, target path

**Staged Sprite File**:
A temporary sibling of the Target Sprite File to which the Lua Operation Kernel saves before SPA validates the Kernel Response, Postconditions, and file. It is replaced into the Target only on success.
_Avoid_: Target Sprite File, backup, exported Artifact

**Target Commit**:
The final replacement of a validated Staged Sprite File into its declared Target Sprite File. A failed mutation or Operation Plan performs no Target Commit.
_Avoid_: Aseprite transaction, save, multi-file transaction

**All-or-Nothing Mutation**:
The public guarantee that an ordinary Mutation Operation resolves and validates its complete target set before changing it, and either reports success for the whole set or performs no Target Commit. It has no skipped-target success branch or generic best-effort mode.
_Avoid_: partial success, warning-only skip, filesystem transaction

**Domain Module**:
The vertical code-ownership boundary for Operations that share domain language and a reason to change. It can contain distinct contract, domain, application, presentation, and Lua binding responsibilities without becoming a logical layer or Bounded Context.
_Avoid_: Command Group, horizontal layer directory, Bounded Context, service

**Paint Operation**:
An agent-facing Operation that expresses raster authoring intent against a selected Cel/Image target, such as applying a bounded pixel patch, drawing a primitive, or filling a region. It changes Image pixels but is not an alternate Image model. When the Image is shared by Linked Cels, the Operation preserves that native sharing and reports every affected Cel.
_Avoid_: per-pixel process call, Image lifecycle operation, generated Lua script

**Raster Authoring Domain Module**:
The Domain Module that owns the shared pixel, color, mask, coordinate, and mutation semantics projected through the `image` and `paint` Command Groups. `image` exposes native Image observation and structural transformation; `paint` exposes authoring intent.
_Avoid_: separate image and paint subsystems, generic graphics engine

**Export Destination**:
The explicit final-file intent for one exported Artifact. It declares a path and `if_exists: fail | replace`. A fixed small output set uses several Destinations; a generated multi-file Operation whose cardinality follows bounded domain inputs can declare an output directory plus an Aseprite-aligned Filename Format from which its complete expected destination set is resolved. A Destination is generated and verified in an operation-owned temporary location before publication and never inherits an editor overwrite preference.
_Avoid_: Target Sprite File, implicit overwrite, Artifact Manifest, backup, general transaction

**Export Image Area**:
The discriminated source area for `export image`: the complete Sprite `canvas`; one explicit positive Canvas Pixel `bounds` Rectangle; or one exactly addressed `slice`, resolved to its effective Slice Key Bounds at the selected Frame. It is rectangular source cropping and never means that a canonical Selection Mask is applied to pixels.
_Avoid_: Selection export, implicit Selection bounds, masked pixels, timeless Slice bounds

**Layer Composition**:
The explicit Layer source for `export image`: `visible` uses persisted effective visibility with optional exact exclusions; `all` renders every natively renderable Layer with optional exact exclusions; and `include` renders a non-empty exact Layer set. Group inclusion/exclusion expands its descendant subtree, required ancestor Groups are enabled for an included child, and native stack, Blend Mode, opacity, Background, Tilemap, and Reference rendering remain Aseprite behavior.
_Avoid_: active Layer, selected Range, Layer glob, custom compositor

**Artifact**:
A file produced and verified by an Operation, represented in its Operation Result by a small value containing `path`, `role`, `format`, `size_bytes`, and `sha256`. Format-specific facts remain in the Operation's own result schema.
_Avoid_: Artifact Record, Artifact Manifest, asset catalog, audit entry

### Product planning

**Aseprite Capability Envelope**:
The business scope shared by Aseprite and SPA: sprite creation, editing, inspection, validation, conversion, and export. SPA can deepen agent-facing automation throughout this envelope but does not take ownership of gameplay, engine integration, art direction, or another product domain.
_Avoid_: thin wrapper, fixed command subset, adjacent game-development platform

**Capability Gap**:
A structured, evidence-backed statement that a capability cannot be implemented through the supported Aseprite public non-interactive editor-command, CLI, or Lua seams for a tested runtime version. `spa info` reports the gap and its reason; an editor UI feature alone is not an automation seam, and SPA does not claim support through GUI driving, private C++ APIs, binary-file patching, or generated operation scripts. New native evidence can reopen the capability.
_Avoid_: permanent product prohibition, silent omission, speculative emulation

**Agent-facing Functional Extension**:
A user-observable capability that composes, controls, observes, or verifies Aseprite behavior so an agent can use it effectively. It extends automation while remaining inside the Aseprite Capability Envelope.
_Avoid_: non-functional infrastructure, unrelated domain feature

**Functional Requirement (FR)**:
A user-observable capability or workflow outcome inside the Aseprite Capability Envelope, including Agent-facing Functional Extensions. Functional coverage is expected to deepen and broaden as evidence-bearing slices are delivered.
_Avoid_: implementation task, quality attribute

**Non-functional Requirement (NFR)**:
A quality constraint that supports an accepted FR. NFR work is discovered and justified through functional development and observed operating needs; it does not establish an independent product or platform roadmap.
_Avoid_: speculative platform capability, premature infrastructure programme
