-- Independent native Image:drawImage oracle for Paint Composite e2e coverage.
assert(BlendMode.HUE and BlendMode.SATURATION and BlendMode.COLOR and BlendMode.LUMINOSITY)
local modes = {
  normal = BlendMode.NORMAL,
  multiply = BlendMode.MULTIPLY,
  screen = BlendMode.SCREEN,
  overlay = BlendMode.OVERLAY,
  darken = BlendMode.DARKEN,
  lighten = BlendMode.LIGHTEN,
  ["color-dodge"] = BlendMode.COLOR_DODGE,
  ["color-burn"] = BlendMode.COLOR_BURN,
  ["hard-light"] = BlendMode.HARD_LIGHT,
  ["soft-light"] = BlendMode.SOFT_LIGHT,
  difference = BlendMode.DIFFERENCE,
  exclusion = BlendMode.EXCLUSION,
  hue = BlendMode.HUE,
  saturation = BlendMode.SATURATION,
  color = BlendMode.COLOR,
  luminosity = BlendMode.LUMINOSITY,
  addition = BlendMode.ADDITION,
  subtract = BlendMode.SUBTRACT,
  divide = BlendMode.DIVIDE,
}
for name, mode in pairs(modes) do
  assert(mode ~= nil, "missing BlendMode: " .. name)
  if name ~= "normal" then
    assert(mode ~= BlendMode.NORMAL, "non-Normal BlendMode aliases Normal: " .. name)
  end
end

local function color(mode, pixel)
  local pc = app.pixelColor
  if mode == "rgb" then
    return {
      kind = "rgba",
      red = pc.rgbaR(pixel),
      green = pc.rgbaG(pixel),
      blue = pc.rgbaB(pixel),
      alpha = pc.rgbaA(pixel),
    }
  end
  return { kind = "grayscale", gray = pc.grayaV(pixel), alpha = pc.grayaA(pixel) }
end

local rgb_back = app.pixelColor.rgba(40, 100, 180, 128)
local rgb_front = app.pixelColor.rgba(210, 50, 20, 128)
local gray_back = app.pixelColor.graya(80, 128)
local gray_front = app.pixelColor.graya(200, 128)
local oracle = { matrix = {}, linked = {}, background = {} }

for _, spec in ipairs {
  { name = "rgb", native = ColorMode.RGB, back = rgb_back, front = rgb_front },
  { name = "grayscale", native = ColorMode.GRAY, back = gray_back, front = gray_front },
} do
  local sprite = Sprite(1, 1, spec.native)
  local destination = assert(sprite.layers[1]:cel(1)).image
  destination:putPixel(0, 0, spec.back)
  local source = Image(destination)
  source:putPixel(0, 0, spec.front)
  assert(sprite:saveAs(assert(app.params[spec.name .. "_file"])))
  oracle.matrix[spec.name] = {}
  for name, mode in pairs(modes) do
    local samples = {}
    for _, opacity in ipairs { 0, 127, 255 } do
      local result = Image(destination)
      result:drawImage(source, Point(0, 0), opacity, mode)
      samples[tostring(opacity)] = color(spec.name, result:getPixel(0, 0))
    end
    oracle.matrix[spec.name][name] = samples
  end
  sprite:close()
end

local linked = Sprite(4, 2, ColorMode.RGB)
local layer = linked.layers[1]
local first = assert(layer:cel(1))
local image = Image(2, 1, ColorMode.RGB)
image:clear(app.pixelColor.rgba(0, 0, 0, 0))
image:putPixel(0, 0, rgb_back)
image:putPixel(1, 0, rgb_back)
first.image = image
first.position = Point(1, 0)
layer.isContinuous = true
linked:newFrame(1)
layer.isContinuous = false
assert(layer:cel(2).image == first.image)
local linked_source = Image(first.image)
linked_source:putPixel(0, 0, rgb_front)
linked_source:putPixel(1, 0, rgb_front)
for x = 0, 1 do
  local result = Image(first.image)
  result:drawImage(linked_source, Point(x, 0), 127, BlendMode.NORMAL)
  oracle.linked[tostring(x)] = color("rgb", result:getPixel(x, 0))
end
assert(linked:saveAs(assert(app.params.linked_file)))
linked:close()

local background = Sprite(1, 1, ColorMode.RGB)
local background_layer = background.layers[1]
local background_image = assert(background_layer:cel(1)).image
background_image:putPixel(0, 0, app.pixelColor.rgba(40, 100, 180, 255))
app.activeSprite = background
app.activeLayer = background_layer
app.bgColor = Color { r = 40, g = 100, b = 180, a = 255 }
app.command.BackgroundFromLayer()
assert(background_layer.isBackground)
local source = Image(background_image)
source:putPixel(0, 0, rgb_front)
local result = Image(background_image)
result:drawImage(source, Point(0, 0), 127, BlendMode.NORMAL)
oracle.background = color("rgb", result:getPixel(0, 0))
assert(background:saveAs(assert(app.params.background_file)))
background:close()

local output = assert(io.open(assert(app.params.oracle), "wb"))
output:write(json.encode(oracle))
output:close()
