-- Observe packaged native Paint in the same editor process, including handled failure.
local paint = dofile(app.params.native_paint)
local function contents(path)
  local file = assert(io.open(path, "rb"))
  local bytes = file:read("*a")
  file:close()
  return bytes
end
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
local native_tool = app.params.tool
local pref = app.preferences.tool(native_tool)
pref.filled, pref.filled_preview, pref.corner_radius = true, true, 4
pref.opacity, pref.brush.size, pref.brush.angle = 13, 9, 25
local flood_preferences = {}
if native_tool == "paint_bucket" then
  for _, name in ipairs { "paint_bucket", "magic_wand" } do
    local flood = app.preferences.tool(name).floodfill
    flood.refer_to, flood.stop_at_grid, flood.pixel_connectivity = 1, 1, 1
    flood_preferences[#flood_preferences + 1] = flood
  end
end
local expected_bytes = layer:cel(1).image.bytes
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
  for _, flood in ipairs(flood_preferences) do
    assert(flood.refer_to == 1 and flood.stop_at_grid == 1 and flood.pixel_connectivity == 1)
  end
  assert(pref.opacity == 13 and pref.brush.size == 9 and pref.brush.angle == 25)
  assert(#app.sprites == count and layer:cel(1).image.bytes == expected_bytes)
  assert(ambient.selection:contains(Point(1, 1)) and not ambient.selection:contains(Point(0, 0)))
end
local request = {
  source_sprite_file = app.params.source,
  staged_sprite_file = app.params.target,
  target = { layer = { layer_path = { 1 } }, frame_number = 1 },
  coordinate_space = "image-pixel",
  brush = { kind = "circle", size = 1 },
  color = { kind = "rgba", red = 255, green = 0, blue = 0, alpha = 255 },
  ink = "simple",
  opacity = native_tool == "eraser" and 255 or 0,
  clipping = "reject",
  ["from"] = { x = 2, y = 2 },
  to = { x = 5, y = 2 },
  bounds = { x = 2, y = 2, width = 4, height = 3 },
  style = native_tool:match("^filled_") and "filled" or "outline",
  points = { { x = 2, y = 2 }, { x = 5, y = 2 }, { x = 2, y = 2 } },
  freehand_algorithm = "regular",
  behavior = { kind = "erase" },
  seed = { x = 0, y = 0 },
  tolerance = 0,
  contiguous = true,
  connectivity = "four-connected",
  refer_to = "active-layer",
  stop_at_grid = false,
}
local result = paint.execute(request, native_tool)
assert(result.persisted_reopen_verified and result.pixels_changed > 0)
assert_restored()
local target_bytes = contents(app.params.target)
request["from"] = { x = -2, y = -2 }
request.to = { x = 1, y = 1 }
request.bounds = { x = -2, y = -2, width = 4, height = 3 }
request.points = { { x = -2, y = -2 }, { x = 1, y = 1 } }
request.seed = { x = -1, y = 0 }
request.staged_sprite_file = app.params.failure
local ok, reason = pcall(paint.execute, request, native_tool)
local expected_error = native_tool == "paint_bucket" and "seed is outside the Sprite Canvas"
  or "footprint is outside Image bounds"
assert(not ok and tostring(reason):find(expected_error, 1, true), tostring(reason))
assert_restored()
assert(not app.fs.isFile(app.params.failure))
-- Aseprite can report saveAs success for an unwritable destination. The
-- subsequent reopen must refuse publication after the native Image was changed.
request["from"], request.to = { x = 2, y = 2 }, { x = 5, y = 2 }
request.bounds = { x = 2, y = 2, width = 4, height = 3 }
request.points = { { x = 2, y = 2 }, { x = 5, y = 2 }, { x = 2, y = 2 } }
request.seed = { x = 0, y = 0 }
-- Interrupt the real drawing seam after the first native footprint invocation.
-- Other editor reads and writes still reach Aseprite, including restoration.
local native_app, invocations = app, 0
app = setmetatable({
  useTool = function(options)
    invocations = invocations + 1
    if invocations == 2 then error("injected native drawing failure") end
    return native_app.useTool(options)
  end,
}, { __index = native_app, __newindex = function(_, key, value) native_app[key] = value end })
ok, reason = pcall(paint.execute, request, native_tool)
app = native_app
assert(
  not ok and tostring(reason):find("injected native drawing failure", 1, true),
  tostring(reason)
)
assert_restored()
assert(not app.fs.isFile(app.params.failure))
request.staged_sprite_file = app.params.unwritable
ok, reason = pcall(paint.execute, request, native_tool)
assert(not ok and tostring(reason):find("could not reopen Native Paint", 1, true))
assert_restored()
assert(contents(app.params.source) == source_bytes)
assert(contents(app.params.target) == target_bytes)
ambient:close()
