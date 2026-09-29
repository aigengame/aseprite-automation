-- Independent Aseprite reference for an ordered Pencil or Eraser gesture.
local file = assert(io.open(app.params.input, "rb"))
local request = json.decode(file:read("*a"))
file:close()

local mode = ({ rgb = ColorMode.RGB, grayscale = ColorMode.GRAY, indexed = ColorMode.INDEXED })[request.mode]
local sprite = Sprite(8, 6, mode)
local layer = sprite.layers[1]
if mode == ColorMode.INDEXED then
  local palette = Palette(8)
  palette:setColor(1, Color { r = 255, g = 0, b = 0, a = 255 })
  palette:setColor(2, Color { r = 0, g = 0, b = 255, a = 255 })
  palette:setColor(3, Color { r = 0, g = 255, b = 0, a = 255 })
  sprite:setPalette(palette)
  sprite.transparentColor = 7
end

local function pixel(kind)
  if mode == ColorMode.RGB then
    return kind == "foreground" and app.pixelColor.rgba(255, 0, 0, 255)
      or app.pixelColor.rgba(0, 255, 0, 255)
  elseif mode == ColorMode.GRAY then
    return kind == "foreground" and app.pixelColor.graya(220, 255) or app.pixelColor.graya(110, 255)
  end
  return kind == "foreground" and 1 or 3
end

layer:cel(1).image:clear(pixel("other"))
for x = 1, 5 do
  layer:cel(1).image:putPixel(x, 2, pixel("foreground"))
end
if not request.background then
  layer:cel(1).image:putPixel(
    7,
    5,
    mode == ColorMode.RGB and app.pixelColor.rgba(0, 0, 0, 0)
      or mode == ColorMode.GRAY and app.pixelColor.graya(0, 0)
      or 7
  )
else
  app.activeSprite, app.activeLayer = sprite, layer
  app.bgColor = mode == ColorMode.RGB and Color { r = 0, g = 0, b = 255 }
    or mode == ColorMode.GRAY and Color { gray = 30 }
    or Color { index = 2 }
  app.command.BackgroundFromLayer()
end
if request.linked then
  layer.isContinuous = true
  sprite:newFrame(1)
  layer.isContinuous = false
  sprite:newEmptyFrame()
  sprite:newCel(layer, 3, Image(layer:cel(1).image), Point(0, 0))
end
assert(sprite:saveAs(app.params.source))

local function native_color(value)
  if value.kind == "rgba" then
    return Color { r = value.red, g = value.green, b = value.blue, a = value.alpha }
  elseif value.kind == "grayscale" then
    return Color { gray = value.gray, alpha = value.alpha }
  end
  return Color { index = value.index }
end

local reference = Sprite(sprite)
local reference_layer = reference.layers[1]
if request.selection then
  local r = request.selection.rectangle
  reference.selection = Selection(Rectangle(r.x, r.y, r.width, r.height))
end
local fg = request.tool == "pencil" and native_color(request.color)
  or request.behavior.kind == "replace-foreground-with-background" and native_color(
    request.behavior.foreground_color
  )
  or native_color(request.fallback_foreground)
local bg = request.tool == "pencil" and fg
  or request.behavior.background_color and native_color(request.behavior.background_color)
  or native_color(request.fallback_background)
local brush = Brush {
  type = ({ circle = BrushType.CIRCLE, square = BrushType.SQUARE, line = BrushType.LINE })[request.brush.kind],
  size = request.brush.size,
  angle = request.brush.angle or 0,
}
local points = {}
for _, point in ipairs(request.points) do
  points[#points + 1] = Point(point.x, point.y)
end
local ink = request.tool == "pencil"
    and ({
      simple = Ink.SIMPLE,
      ["alpha-compositing"] = Ink.ALPHA_COMPOSITING,
      ["copy-color"] = Ink.COPY_COLOR,
      ["lock-alpha"] = Ink.LOCK_ALPHA,
    })[request.ink]
  or nil
local algorithm = ({ regular = 0, ["pixel-perfect"] = 1, dots = 2 })[request.algorithm]
local old_bg = app.bgColor
if request.tool == "eraser" and request.background and request.behavior.kind == "erase" then
  app.bgColor = bg
end
app.useTool {
  tool = request.tool,
  layer = reference_layer,
  frame = reference.frames[1],
  color = fg,
  bgColor = bg,
  brush = brush,
  ink = ink,
  button = request.tool == "eraser"
      and request.behavior.kind == "replace-foreground-with-background"
      and MouseButton.RIGHT
    or MouseButton.LEFT,
  opacity = request.opacity,
  freehandAlgorithm = algorithm,
  points = points,
}
app.bgColor = old_bg
reference.selection = Selection()
assert(reference:saveAs(app.params.reference))
reference:close()
sprite:close()
