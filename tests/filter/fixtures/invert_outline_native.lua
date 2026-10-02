-- Independent native command oracle; constants come from Aseprite's native headers.
local sprite = assert(app.open(app.params.source))
app.activeSprite = sprite
app.activeLayer = sprite.layers[1]
app.activeFrame = sprite.frames[1]
app.range:clear()
app.range.layers = { sprite.layers[1] }
app.range.frames = { 1 }
app.range.colors = {}
if app.params.selection == "center" then
  sprite.selection = Selection(Rectangle(2, 2, 1, 1))
elseif app.params.selection == "empty" then
  sprite.selection = Selection()
else
  sprite.selection = Selection(Rectangle(0, 0, 5, 5))
end
local flags = tonumber(app.params.channels)
if app.params.operation == "invert-color" then
  assert(app.command.InvertColor { ui = false, channels = flags })
else
  local outline, background
  if sprite.colorMode == ColorMode.INDEXED then
    outline, background = Color { index = 126 }, Color { index = 129 }
  elseif sprite.colorMode == ColorMode.GRAY then
    outline, background = Color { gray = 211, alpha = 203 }, Color { gray = 19, alpha = 255 }
  else
    outline, background =
      Color { r = 211, g = 157, b = 89, a = 203 }, Color { r = 19, g = 23, b = 29, a = 255 }
  end
  assert(
    app.command.Outline {
      ui = false,
      channels = flags,
      place = tonumber(app.params.place),
      matrix = tonumber(app.params.matrix),
      tiledMode = tonumber(app.params.tiled),
      color = outline,
      bgColor = background,
    }
  )
end
assert(sprite:saveAs(app.params.target))
sprite:close()
