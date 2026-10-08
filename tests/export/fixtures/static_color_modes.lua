-- Neutral channels distinguish conversion, Palette selection, and opacity behavior.
local scenario = app.params.scenario or "basic"
local modes = { rgb = ColorMode.RGB, grayscale = ColorMode.GRAY, indexed = ColorMode.INDEXED }
local mode = modes[app.params.mode or "rgb"]
local width = scenario == "dither" and 8 or (scenario == "selection" and 4 or 2)
local height = scenario == "dither" and 4 or 1
local sprite = Sprite(width, height, mode)
sprite:assignColorSpace(ColorSpace())
sprite.transparentColor = 0
local palette = Palette(4)
palette:setColor(0, Color { r = 0, g = 0, b = 0, a = 0 })
palette:setColor(1, Color { r = 90, g = 90, b = 90, a = scenario == "semi" and 128 or 255 })
palette:setColor(2, Color { r = 180, g = 180, b = 180, a = 255 })
palette:setColor(3, Color { r = 240, g = 240, b = 240, a = 128 })
if scenario == "dither" then
  palette:resize(3)
  palette:setColor(1, Color { r = 0, g = 0, b = 0, a = 255 })
  palette:setColor(2, Color { r = 255, g = 255, b = 255, a = 255 })
end
sprite:setPalette(palette)
local image = sprite.cels[1].image
if scenario == "dither" then
  assert(mode == ColorMode.RGB)
  for y = 0, height - 1 do
    for x = 0, width - 1 do
      local gray = 24 + x * 29
      image:putPixel(x, y, app.pixelColor.rgba(gray, gray, gray, 255))
    end
  end
elseif scenario == "selection" then
  assert(mode == ColorMode.RGB)
  image:putPixel(0, 0, app.pixelColor.rgba(255, 0, 0, 255))
  image:putPixel(1, 0, app.pixelColor.rgba(0, 255, 0, 255))
  image:putPixel(2, 0, app.pixelColor.rgba(10, 10, 10, 255))
  image:putPixel(3, 0, app.pixelColor.rgba(20, 20, 20, 255))
  sprite:newEmptyFrame()
  local second = Image(image)
  second:putPixel(0, 0, app.pixelColor.rgba(0, 0, 255, 255))
  second:putPixel(1, 0, app.pixelColor.rgba(255, 0, 255, 255))
  second:putPixel(2, 0, app.pixelColor.rgba(70, 70, 70, 255))
  second:putPixel(3, 0, app.pixelColor.rgba(130, 130, 130, 255))
  sprite:newCel(sprite.layers[1], 2, second)
elseif mode == ColorMode.RGB then
  image:putPixel(0, 0, app.pixelColor.rgba(90, 90, 90, 255))
elseif mode == ColorMode.GRAY then
  image:putPixel(0, 0, app.pixelColor.graya(90, 255))
else
  image:putPixel(0, 0, 1)
end
assert(sprite:saveAs(app.params.out))
sprite:close()
