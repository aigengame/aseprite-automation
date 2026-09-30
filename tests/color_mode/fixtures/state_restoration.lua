local color_mode = dofile(app.params.color_mode)
local source = assert(app.open(app.params.source))
local sentinel = Sprite(2, 2, ColorMode.RGB)
sentinel:newEmptyFrame()
app.activeSprite, app.activeLayer, app.activeFrame =
  sentinel, sentinel.layers[1], sentinel.frames[2]
app.fgColor = Color { r = 10, g = 20, b = 30, a = 255 }
app.bgColor = Color { r = 40, g = 50, b = 60, a = 255 }
local foreground, background = app.fgColor, app.bgColor
local function unchanged()
  assert(app.activeSprite == sentinel and app.activeLayer == sentinel.layers[1])
  assert(app.activeFrame == sentinel.frames[2])
  assert(app.fgColor == foreground and app.bgColor == background)
end
local function indexed(matrix)
  return {
    source_color_mode = "rgb",
    target = {
      color_mode = "indexed",
      rgb_map_algorithm = "default",
      color_best_fit_criteria = "default",
      dithering = { algorithm = "ordered", matrix = matrix },
    },
  }
end
local failed =
  color_mode.change(source, indexed { kind = "file", path = app.params.invalid_matrix })
assert(failed.rejection.code == "dithering_matrix_invalid")
assert(source.colorMode == ColorMode.RGB)
unchanged()
local result = color_mode.change(source, indexed { kind = "installed", id = "bayer4x4" })
assert(result.changed and source.colorMode == ColorMode.INDEXED)
unchanged()
source:close()
sentinel:close()
