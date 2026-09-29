-- Observe packaged native Paint in the same editor process, including handled failure.
local paint = dofile(app.params.native_paint)
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
  opacity = 0,
  clipping = "reject",
  ["from"] = { x = 2, y = 2 },
  to = { x = 5, y = 2 },
  bounds = { x = 2, y = 2, width = 4, height = 3 },
  style = native_tool:match("^filled_") and "filled" or "outline",
}
local result = paint.execute(request, native_tool)
assert(result.persisted_reopen_verified and result.pixels_changed > 0)
assert_restored()
request["from"] = { x = -2, y = -2 }
request.to = { x = 1, y = 1 }
request.bounds = { x = -2, y = -2, width = 4, height = 3 }
request.staged_sprite_file = app.params.failure
local ok, reason = pcall(paint.execute, request, native_tool)
assert(not ok and tostring(reason):find("footprint is outside Image bounds", 1, true))
assert_restored()
assert(not app.fs.isFile(app.params.failure))
ambient:close()
