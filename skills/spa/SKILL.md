---
name: spa
description: Use the spa CLI to create, edit, inspect, validate, and export Aseprite assets. Use when an agent works on sprites, pixel art, animations, or tile assets through Aseprite, or the user asks for SPA automation.
---

# spa

`spa` is an agent-facing CLI for Aseprite. Use it to prepare raster inputs,
create and edit native sprite files, inspect the result, and export assets
for another tool or game engine. SPA and Aseprite must be installed separately;
installing this skill does not install either executable.

## Configure and discover

- Set `SPA_ASEPRITE_EXECUTABLE` to the Aseprite executable, or pass
  `--aseprite PATH` on an operation, such as `spa info --aseprite PATH`.
- Run `spa version` to identify the installed CLI and `spa info` to check
  the selected Aseprite runtime. Keep the same runtime for related calls.
- Use `spa --help` for command groups, `spa <group> --help` for commands,
  and `spa <group> <command> --help` for usage. Read that command's
  `--schema` for request fields, results, and failures. Use `spa schema`
  when you need the full installed surface and declared Capability Gaps.
- Follow the installed help and schemas when they differ from an example.
  Check that the operation and options needed for the task are available.
  If they are absent or unclear, report the limitation instead of inventing
  a command or assuming that a newer example applies.

Operations emit JSON by default. Build the request from the command's
schema; send a short object with `--input-json '{...}'`, or use stdin:

```bash
spa sprite create --schema
spa sprite create --input-json - < create.json
```

Read the JSON `status` and the operation's result fields. On failure, use
the top-level `code` and `details`; use `message` and `diagnostics` for
explanation. `--human` is an optional readable view of the same outcome.

## Create, edit, and verify

1. For a new asset, use `sprite create` with the requested dimensions,
   color mode, and initial layer. For an existing asset, inspect it with
   `sprite get` and the relevant Layer, Frame, or Cel commands before
   editing. Request only the inspection sections needed for the task.
2. Choose explicit source and target files. When keeping an original,
   write to a separate target and continue from the file just produced.
   Use in-place editing or overwrite only when the task calls for it;
   do not enable them merely to get past a refusal.
3. Discover the relevant authoring commands for the change. Use inspected
   layer addresses and frame numbers rather than assuming names are unique
   or positions have stayed the same. SPA Frame Numbers start at 1; follow
   the schema's coordinate space for pixel or tile edits.
4. Inspect the saved result and validate the facts the task requires.
   For `sprite validate`, supply the expected facts and check `valid`,
   `checks`, and `findings`: `status: success` means the check ran, not
   that the sprite matched. A successful command alone does not establish
   visual quality; preview the exported image when appearance matters.

For several supported changes to one sprite, consider `plan check` and
`plan run` to avoid repeated saves. Discover which operations can be steps
before building a plan. A plan does not coordinate several sprite files.

For external PNG artwork, discover `raster prepare` and `image import`
before rebuilding the image through individual paint calls. Keep the
preparation, authoring, and export choices explicit in their requests.

## Export and recover

Use `export --help` to choose an installed output operation. For a first
image, inspect `export image --schema`, select the frame, area, layers,
color handling, and destination required by the task, then export. Use
the returned Artifact paths; retain the editable sprite when the task
calls for reusable source assets. Check the actual image and metadata
needed by the downstream consumer. A successful export does not prove
that a game engine imported or used it correctly.

When a request fails, use its typed details to correct the input or
environment before retrying. If a multi-file export reports
`partial_publication`, inspect the per-destination results and existing
files first; a retry must account for outputs already written. For a
Capability Gap or unavailable operation, explain the affected part of
the task and any supported alternative without silently changing the
requested result. `script run` is for an explicit caller-owned Lua task;
it is not a fallback to bypass an unavailable or refused operation.
