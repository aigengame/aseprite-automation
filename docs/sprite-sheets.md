# Sprite Sheet export

`spa export sheet` publishes a PNG texture and Aseprite JSON Array metadata. The
installed `--schema` defines request, Result and Failure fields. This is an Export
Operation; it does not modify the Source Sprite and is not a Plan Step.

```sh
spa export sheet --input-json '{
  "source_sprite_file":"wizard.aseprite",
  "image_destination":{"path":"wizard.png","if_exists":"fail"},
  "metadata_destination":{"path":"wizard.json","if_exists":"fail"},
  "selection":{"kind":"range","from_frame":1,"to_frame":8},
  "layer_composition":{"mode":"visible"},
  "output_color_mode":"rgb",
  "layout":{"kind":"rows","columns":4},
  "trim":"frame",
  "padding":{"border":1,"shape":1,"inner":0},
  "filename_format":"wizard_{frame0001}"
}'
```

Each destination requires its own `fail` or `replace` intent and an existing parent
directory. The image extension is `.png`; metadata is `.json`. Source aliases and
colliding publication paths fail before runtime work. `meta.image` is relative to
the final metadata directory, including when the two files use different directories.

## Logical Frames and physical rectangles

Select an ordered, inclusive, one-based Frame Range, or use
`{"kind":"tag","tag":{"tag_name":"cast"}}`. An exact `tag_index` is also
supported. Ambiguous names fail. The sheet includes each selected Source Frame once
in timeline order; Tag direction and repeats do not expand playback.

Each Frame retains its own record and duration. Native duplicate sharing can assign
the same physical rectangle to several records, including blank Frames. Consumers
must iterate the records, not unique rectangles. Per-Frame blank content is a 1×1
transparent image; padding can enlarge its atlas rectangle.

Only Tags wholly inside the selected range appear in `meta.frameTags`. Their `from`
and `to` fields address output records from zero. Crossing Tags are omitted rather
than clipped. The Result retains original Source Tag facts and Source Frame numbers.
Native JSON uses `repeat` as a string for nonzero repeats and omits zero repeats;
the typed Result retains the original integer. Stored zero does not mean infinite
output Frames.

`filename_format` is literal prefix/suffix text around exactly one ordinal token:
`{frame0}`, `{frame1}`, `{frame0000}`, or `{frame0001}`, for example. The trailing
digit sets the start at zero or one; leading zeros set minimum width. Names refer to
output order. They are metadata names, not generated file paths. Other placeholders
are rejected.

## Layout and trim

| Layout | Parameters |
| --- | --- |
| `horizontal`, `vertical`, `packed` | `kind` only |
| `rows` | Positive `columns` count |
| `columns` | Positive `rows` count |

Aseprite computes dimensions and placement. Duplicate sharing is enabled; packed
also shares duplicates natively. There is no fixed texture size or pagination.
Each padding value is an integer from 0 through 100. `border` surrounds the atlas,
`shape` separates physical images, and `inner` surrounds each image inside its
reported `frame` rectangle. `spriteSourceSize` still describes content, without
inner padding.

- `none`: retain the Canvas.
- `sprite`: one native common trim rectangle, computed across the **whole Source
  timeline** under the selected composition, including unselected Frames. Native
  trim can remove solid-color opaque borders as well as transparent borders.
- `frame`: native per-Frame trim, including its different border reference when a
  Background participates.

Offsets and original sizes retain placement information. They do not restore pixels
deliberately removed by native trim. The Result reports the common rectangle when used.

## Composition, color and profiles

`visible` follows saved visibility. `include` reuses exact Layer/Group addressing;
a Group includes hidden descendants and ancestor opacity/Blend Mode context while
excluding other branches. Native Image, Group, Background and Tilemap composition
are reused. Reference content is excluded; directly selecting a Reference Layer
fails explicitly.

Require `output_color_mode` on every request:

- `rgb`: native visual RGBA rendering with each Frame's Effective Palette, before
  duplicate comparison. RGB, Grayscale and Indexed Sources are accepted. Linked
  Cels with Palette Changes can therefore produce distinct atlas images.
- `indexed`: require an Indexed Source and the same complete ordered Effective
  Palette for every selected Frame. Preserve indexes, duplicate and unused entries.
  Require 1–256 entries, a defined Transparent Color Index and defined output indexes.
  Palette Changes outside the selection do not themselves cause refusal.

Indexed PNG preserves Palette RGB and alpha except that the Transparent Color Index
is encoded with alpha zero. If retained Background pixels would lose visible alpha,
the request fails. This check uses the declared trim result; Background presence
alone is not a refusal. SPA does not quantize, remap or switch to RGB implicitly.

Preserve None, sRGB, or the exact packaged linear-sRGB/Display P3 ICC profiles from
the Color Profile capability. Unknown profiles fail. Source channels are not
converted. PNG sRGB rendering intent is normalized to zero by Aseprite and reported;
ICC payloads are checked byte for byte.

## Verification and failure

Both files are staged. An independent PNG decoder and JSON parser check each logical
Frame against native samples captured before layout: pixels/indexes, Palette, profile,
duration, name, trim, placement, padding and Tag projection. The common trim rectangle
is observed through a separate unpadded native export of one selected Frame, using
the same whole rendered timeline. SPA does not implement a cropper, packer or renderer.

No final file is published before the complete pair passes. Publication order is image,
then metadata. If the second publication fails, `partial_publication` reports each
normalized destination, previous existence, publication state and replacement facts.
Already published files are not rolled back. Other failures use the installed typed
Failure schema. The successful Result contains requested parameters, effective image
and Frame facts, and two Artifacts with sizes and SHA-256 digests.

Current Operation Limits admit at most 16,777,216 rendered timeline pixels. Common
trim counts the whole timeline; other modes count selected Frames. Before native
allocation, an untrimmed padded atlas bound must also fit 65,535 pixels per side and
16,777,216 pixels in area. Packed uses the sum of sample extents on both axes as a
conservative bound; some sheets that would pack smaller are refused. Row/column counts
are at most 65,535. A limit refusal reports the applicable bound; it does not paginate
or silently reduce the request.

These are current feature and execution boundaries. Future demand can extend them
through explicit contracts and validated native paths. See
[#48](https://github.com/aigengame/aseprite-automation/issues/48) and
[ADR-0085](adr/0085-stage-and-verify-explicit-export-destinations.md).
