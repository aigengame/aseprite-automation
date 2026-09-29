-- Two small authored subjects with distinct per-Frame geometry and stored pixels.
local modes = { rgb = ColorMode.RGB, grayscale = ColorMode.GRAY, indexed = ColorMode.INDEXED }
local mode = modes[app.params.mode or "rgb"]
local sprite = Sprite(24, 20, mode)
if mode == ColorMode.INDEXED then sprite.transparentColor = tonumber(app.params.mask or "0") end
local layer = sprite.layers[1]
layer.name = app.params.artwork or "wizard"
local durations = { 100, 300, 80, 275, 600 }
local count = tonumber(app.params.frame_count or "5")
for number = 2, count do
  sprite:newEmptyFrame(number)
end
for number = 1, count do
  sprite.frames[number].duration = durations[(number - 1) % 5 + 1] / 1000
  local spec = sprite.spec
  spec.width = 8 + number % 2
  spec.height = 12
  local image = Image(spec)
  local function pixel(x, y, shade, alpha)
    local value
    if mode == ColorMode.RGB then
      value = app.pixelColor.rgba(17 * number + shade, 29 + y, 53 + x, alpha)
    elseif mode == ColorMode.GRAY then
      value = app.pixelColor.graya(17 * number + shade, alpha)
    else
      value = alpha == 0 and sprite.transparentColor or 17 * number + shade
    end
    image:drawPixel(x, y, value)
  end
  for y = 1, 10 do
    for x = 1, 6 do
      if app.params.artwork == "emblem" then
        if math.abs(x - 3) + math.abs(y - 5) <= 2 + number % 2 then pixel(x, y, 3, 255) end
      elseif
        (y <= 3 and math.abs(x - 3) <= y - 1)
        or (y >= 4 and y <= 10 and x >= 2 and x <= 4)
        or (x == 6 and y >= 3 + number % 3)
      then
        pixel(x, y, y < 4 and 1 or y < 6 and 7 or 4, 255)
      end
    end
  end
  pixel(0, 0, 2, 0) -- Hidden RGB/gray data must survive motion and native save/reopen.
  local cel = sprite:newCel(layer, number, image, Point(number - 3, 3 - number))
  cel.opacity = (20 * number) % 256
  cel.zIndex = number - 3
end
local other = sprite:newLayer()
other.name = "untouched"
sprite:newCel(other, 1, layer:cel(1).image, Point(2, 4))
if app.params.kind == "linked" then
  app.activeSprite = sprite
  app.activeLayer = layer
  app.activeFrame = sprite.frames[1]
  app.range:clear()
  app.command.NewFrame { content = "cellinked" }
elseif app.params.kind == "missing" then
  sprite:deleteCel(layer, 5)
elseif app.params.kind == "boundary" then
  layer:cel(1).position = Point(-32768, 32767)
end
layer.isVisible = false
layer.isEditable = false
assert(sprite:saveAs(app.params.out))
sprite:close()
