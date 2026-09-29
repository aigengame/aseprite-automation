-- Independent native Fill fixture and oracle. Matching uses Aseprite tools only.
local file = assert(io.open(app.params.input, "rb"))
local request = json.decode(file:read("*a"))
file:close()

local mode = assert(
  ({ rgb = ColorMode.RGB, grayscale = ColorMode.GRAY, indexed = ColorMode.INDEXED })[request.mode]
)
local sprite = Sprite(8, 6, mode)
local layer = sprite.layers[1]
if mode == ColorMode.INDEXED then
  local palette = Palette(8)
  palette:setColor(1, Color { r = 240, g = 20, b = 20, a = 255 })
  palette:setColor(2, Color { r = 20, g = 20, b = 240, a = 255 })
  palette:setColor(3, Color { r = 20, g = 220, b = 20, a = 255 })
  palette:setColor(7, Color { r = 0, g = 0, b = 0, a = 0 })
  sprite:setPalette(palette)
  sprite.transparentColor = 7
end

local function pixel(kind)
  if mode == ColorMode.RGB then
    if kind == "mark" then return app.pixelColor.rgba(240, 20, 20, 255) end
    if kind == "near" then return app.pixelColor.rgba(220, 20, 20, 255) end
    if kind == "paint" then return app.pixelColor.rgba(20, 220, 20, 255) end
    if kind == "empty" then return app.pixelColor.rgba(0, 0, 0, 0) end
    return app.pixelColor.rgba(20, 20, 240, 255)
  elseif mode == ColorMode.GRAY then
    if kind == "mark" then return app.pixelColor.graya(220, 255) end
    if kind == "near" then return app.pixelColor.graya(200, 255) end
    if kind == "paint" then return app.pixelColor.graya(110, 255) end
    if kind == "empty" then return app.pixelColor.graya(0, 0) end
    return app.pixelColor.graya(40, 255)
  end
  return ({ mark = 1, near = 3, paint = 3, empty = 7, base = 2 })[kind]
end

local function color(kind)
  if mode == ColorMode.RGB then
    if kind == "mark" then return Color { r = 240, g = 20, b = 20, a = 255 } end
    return Color { r = 20, g = 220, b = 20, a = 255 }
  elseif mode == ColorMode.GRAY then
    if kind == "mark" then return Color { gray = 220, alpha = 255 } end
    return Color { gray = 110, alpha = 255 }
  end
  return Color { index = kind == "mark" and 1 or 3 }
end

local scenario = request.scenario or "diagonal"
local target = assert(layer:cel(1))
if scenario == "small" then
  target.image = Image(3, 2, mode)
  target.position = Point(2, 1)
  target.image:clear(pixel("empty"))
  target.image:putPixel(1, 0, pixel("mark"))
else
  target.image:clear(pixel("base"))
  if
    scenario ~= "all"
    and scenario ~= "all-frame2"
    and scenario ~= "uniform"
    and scenario ~= "frame2"
  then
    for i = 1, 4 do
      target.image:putPixel(i, i, pixel("mark"))
    end
  end
  if scenario == "tolerance" then target.image:putPixel(1, 2, pixel("near")) end
end

if scenario == "all" or scenario == "all-frame2" then
  local visible = sprite:newLayer()
  local overlay = Image(8, 6, mode)
  overlay:clear(pixel("mark"))
  overlay:putPixel(2, 2, pixel("base"))
  sprite:newCel(visible, 1, overlay, Point(0, 0))
  local hidden = sprite:newLayer()
  local hidden_image = Image(8, 6, mode)
  hidden_image:clear(pixel("paint"))
  sprite:newCel(hidden, 1, hidden_image, Point(0, 0))
  hidden.isVisible = false
  if scenario == "all-frame2" then
    sprite:newEmptyFrame()
    local second_target = Image(8, 6, mode)
    second_target:clear(pixel("base"))
    sprite:newCel(layer, 2, second_target, Point(0, 0))
    local second_overlay = Image(8, 6, mode)
    second_overlay:clear(pixel("base"))
    second_overlay:putPixel(2, 2, pixel("mark"))
    second_overlay:putPixel(3, 2, pixel("mark"))
    sprite:newCel(visible, 2, second_overlay, Point(0, 0))
    sprite:newCel(hidden, 2, hidden_image, Point(0, 0))
  end
end

if scenario == "frame2" then
  sprite:newEmptyFrame()
  local image = Image(8, 6, mode)
  image:clear(pixel("base"))
  for i = 1, 4 do
    image:putPixel(i, i, pixel("mark"))
  end
  sprite:newCel(layer, 2, image, Point(0, 0))
end
if request.linked then
  layer.isContinuous = true
  sprite:newFrame(1)
  layer.isContinuous = false
  assert(layer:cel(1).image == layer:cel(2).image)
end
if request.background then
  app.activeSprite, app.activeLayer = sprite, layer
  app.bgColor = color("paint")
  app.command.BackgroundFromLayer()
  assert(layer.isBackground)
end

local grid = request.grid or { x = 1, y = 1, width = 3, height = 3 }
sprite.gridBounds = Rectangle(grid.x, grid.y, grid.width, grid.height)
assert(sprite:saveAs(app.params.source))
sprite:close()

local original = assert(app.open(app.params.source))
local frame = request.frame or 1
local original_cel = assert(original.layers[1]:cel(frame))
local scratch = Sprite(original)
scratch.gridBounds = original.gridBounds
scratch.selection = Selection()
local scratch_cel = assert(scratch.layers[1]:cel(frame))
local seed =
  Point(request.seed.x + original_cel.position.x, request.seed.y + original_cel.position.y)
local refer = request.refer_to == "all-layers" and 1 or 0
local stop = request.stop_at_grid and 2 or 0
local connectivity = request.connectivity == "eight-connected" and 1 or 0

local function use(tool, ink, opacity)
  local flood = app.preferences.tool(tool).floodfill
  flood.refer_to = refer
  flood.stop_at_grid = stop
  flood.pixel_connectivity = connectivity
  app.activeSprite, app.activeLayer, app.activeFrame =
    scratch, scratch.layers[1], scratch.frames[frame]
  app.useTool {
    tool = tool,
    cel = scratch_cel,
    layer = scratch.layers[1],
    frame = scratch.frames[frame],
    points = { seed },
    color = color(request.paint_color or "paint"),
    ink = ink,
    opacity = opacity,
    tolerance = request.tolerance,
    contiguous = request.contiguous,
    selection = SelectionMode.REPLACE,
  }
end

use("magic_wand", Ink.SIMPLE, 255)
local footprint = Selection()
footprint:select(scratch.selection)
scratch.selection = Selection()
local inks = {
  simple = Ink.SIMPLE,
  ["alpha-compositing"] = Ink.ALPHA_COMPOSITING,
  ["copy-color"] = Ink.COPY_COLOR,
  ["lock-alpha"] = Ink.LOCK_ALPHA,
}
use("paint_bucket", assert(inks[request.ink]), request.opacity)

local function native_pixel(cel, x, y)
  if cel == nil then return pixel("empty") end
  local image = cel.image
  local local_x, local_y = x - cel.position.x, y - cel.position.y
  if local_x < 0 or local_y < 0 or local_x >= image.width or local_y >= image.height then
    return pixel("empty")
  end
  return image:getPixel(local_x, local_y)
end

local function selected(x, y)
  local mask = request.selection
  if not mask then return true end
  if mask.kind == "all" then
    local r = mask.rectangle
    return x >= r.x and y >= r.y and x < r.x + r.width and y < r.y + r.height
  end
  if mask.kind == "mask" then
    for _, row in ipairs(mask.rows) do
      if row.y == y then
        for _, run in ipairs(row.runs) do
          if x >= run.x and x < run.x + run.length then return true end
        end
      end
    end
  end
  return false
end

local requested, applied, clipped, excluded = {}, {}, {}, {}
local source_image = original_cel.image
for y = 0, original.height - 1 do
  for x = 0, original.width - 1 do
    if footprint:contains(Point(x, y)) then
      local point = { x = x - original_cel.position.x, y = y - original_cel.position.y }
      requested[#requested + 1] = point
      if
        point.x < 0
        or point.y < 0
        or point.x >= source_image.width
        or point.y >= source_image.height
      then
        clipped[#clipped + 1] = point
      elseif not selected(x, y) then
        excluded[#excluded + 1] = point
      else
        applied[#applied + 1] = point
        source_image:putPixel(point.x, point.y, native_pixel(scratch_cel, x, y))
      end
    end
  end
end
local output = assert(io.open(app.params.oracle, "wb"))
output:write(json.encode {
  requested = requested,
  applied = applied,
  clipped = clipped,
  excluded = excluded,
  grid = {
    x = original.gridBounds.x,
    y = original.gridBounds.y,
    width = original.gridBounds.width,
    height = original.gridBounds.height,
  },
})
output:close()
assert(original:saveAs(app.params.reference))
scratch:close()
original:close()
