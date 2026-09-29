-- Exercise one packaged gesture in the same process as disturbed editor state.
local paint = dofile(app.params.native_paint)

local function contents(path)
  local file = assert(io.open(path, "rb"))
  local bytes = file:read("*a")
  file:close()
  return bytes
end

local source = Sprite(8, 6, ColorMode.RGB)
local image = source.layers[1]:cel(1).image
for y = 0, 5 do
  for x = 0, 7 do
    image:putPixel(
      x,
      y,
      app.pixelColor.rgba(
        (x * x * 37 + y * y * 19 + x * y * 11) % 256,
        (x * x * 17 + y * y * 43 + x * y * 7) % 256,
        (x * x * 61 + y * y * 29 + x * y * 5) % 256,
        255
      )
    )
  end
end
assert(source:saveAs(app.params.source))
source:close()
local source_bytes = contents(app.params.source)

local ambient = Sprite(3, 3, ColorMode.RGB)
ambient.selection = Selection(Rectangle(1, 1, 1, 1))
local layer, frame = ambient.layers[1], ambient.frames[1]
app.activeSprite, app.activeLayer, app.activeFrame = ambient, layer, frame
app.fgColor = Color { r = 17, g = 29, b = 41, a = 127 }
app.bgColor = Color { r = 51, g = 63, b = 75, a = 255 }
app.tool = "eraser"
app.brush = Brush { type = BrushType.LINE, size = 7, angle = 35 }
local fg, bg = app.fgColor, app.bgColor
local tool, brush = app.tool.id, app.brush
local doc = app.preferences.document(ambient)
doc.grid.snap = true
doc.tiled.mode = 3
doc.symmetry.mode = 3
app.preferences.symmetry_mode.enabled = true
local count = #app.sprites
local pref = app.preferences.tool(app.params.tool)
pref.filled, pref.filled_preview, pref.corner_radius = true, true, 4
pref.opacity, pref.brush.size, pref.brush.angle = 13, 9, 25
local pencil_pref
if app.params.tool == "blur" then
  pencil_pref = app.preferences.tool("pencil")
  pencil_pref.filled, pencil_pref.filled_preview, pencil_pref.corner_radius = true, true, 6
end
local ambient_bytes = layer:cel(1).image.bytes

local function assert_restored()
  assert(app.activeSprite == ambient and app.activeLayer == layer and app.activeFrame == frame)
  assert(app.tool.id == tool)
  assert(
    app.brush.type == brush.type and app.brush.size == brush.size and app.brush.angle == brush.angle
  )
  assert(app.fgColor == fg and app.bgColor == bg)
  assert(doc.grid.snap and doc.tiled.mode == 3 and doc.symmetry.mode == 3)
  assert(app.preferences.symmetry_mode.enabled)
  assert(pref.filled and pref.filled_preview and pref.corner_radius == 4)
  assert(pref.opacity == 13 and pref.brush.size == 9 and pref.brush.angle == 25)
  if pencil_pref then
    assert(pencil_pref.filled and pencil_pref.filled_preview and pencil_pref.corner_radius == 6)
  end
  assert(#app.sprites == count and layer:cel(1).image.bytes == ambient_bytes)
  assert(ambient.selection:contains(Point(1, 1)) and not ambient.selection:contains(Point(0, 0)))
  assert(contents(app.params.source) == source_bytes)
end

local native_tool = app.params.tool
local request = {
  source_sprite_file = app.params.source,
  staged_sprite_file = app.params.target,
  target = { layer = { layer_path = { 1 } }, frame_number = 1 },
  coordinate_space = "image-pixel",
  points = native_tool == "blur" and {
    { x = 0, y = 1 },
    { x = 1, y = 1 },
    { x = 1, y = 2 },
    { x = 0, y = 2 },
  } or {
    { x = 2, y = 1 },
    { x = 5, y = 1 },
    { x = 5, y = 4 },
    { x = 2, y = 4 },
  },
  brush = { kind = "circle", size = native_tool == "blur" and 3 or 1 },
  opacity = 128,
  freehand_algorithm = "pixel-perfect",
  clipping = "reject",
}
if native_tool == "blur" then
  request.tiled_mode = "x"
else
  request.color = { kind = "rgba", red = 255, green = 0, blue = 0, alpha = 255 }
  request.ink = "simple"
end

local result = paint.execute(request, native_tool)
assert(result.persisted_reopen_verified and result.pixels_changed > 0)
assert_restored()
local target_bytes = contents(app.params.target)
local good_points = request.points

request.points = { { x = -3, y = -3 }, { x = -2, y = -2 } }
if native_tool == "blur" then request.tiled_mode = "none" end
request.staged_sprite_file = app.params.failure
local ok, reason = pcall(paint.execute, request, native_tool)
assert(not ok and tostring(reason):find("footprint is outside Image bounds", 1, true))
assert_restored()
assert(not app.fs.isFile(app.params.failure))
assert(contents(app.params.target) == target_bytes)

-- app is a Lua table in this runtime. Let both real native tool calls complete,
-- then fail before the adapter can return the clone's changed pixels.
request.points = good_points
if native_tool == "blur" then request.tiled_mode = "x" end
request.staged_sprite_file = app.params.midway
local native_use_tool = app.useTool
assert(rawget(app, "useTool") == nil)
local calls = 0
local saw_requested_tiled_mode = false
rawset(app, "useTool", function(options)
  calls = calls + 1
  if native_tool == "blur" and options.tool == "blur" then
    assert(app.preferences.document(options.cel.sprite).tiled.mode == 1)
    saw_requested_tiled_mode = true
  end
  native_use_tool(options)
  if calls == 2 then error("injected after native clone invocation") end
end)
ok, reason = pcall(paint.execute, request, native_tool)
rawset(app, "useTool", nil)
assert(app.useTool == native_use_tool)
assert(calls == 2 and not ok)
if native_tool == "blur" then assert(saw_requested_tiled_mode) end
assert(tostring(reason):find("injected after native clone invocation", 1, true))
assert_restored()
assert(not app.fs.isFile(app.params.midway))
assert(contents(app.params.target) == target_bytes)

request.staged_sprite_file = app.params.unwritable
ok, reason = pcall(paint.execute, request, native_tool)
assert(not ok and tostring(reason):find("could not reopen Native Paint", 1, true))
assert_restored()
assert(contents(app.params.target) == target_bytes)
ambient:close()
