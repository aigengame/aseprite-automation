-- Deliberately distinct visible colors in two Frames plus an excluded hidden color.
local mode = ({ rgb = ColorMode.RGB, grayscale = ColorMode.GRAY, indexed = ColorMode.INDEXED })[app.params.mode]
local sprite = Sprite(3, 1, mode)
local layer = sprite.layers[1]
local first = layer:cel(1).image
local second = Image(first)
if mode == ColorMode.RGB then
  first:drawPixel(0, 0, app.pixelColor.rgba(255, 0, 0, 255))
  first:drawPixel(1, 0, app.pixelColor.rgba(0, 255, 0, 128))
  second:drawPixel(0, 0, app.pixelColor.rgba(0, 0, 255, 255))
  second:drawPixel(1, 0, app.pixelColor.rgba(255, 255, 255, 255))
elseif mode == ColorMode.GRAY then
  first:drawPixel(0, 0, app.pixelColor.graya(20, 255))
  first:drawPixel(1, 0, app.pixelColor.graya(70, 128))
  second:drawPixel(0, 0, app.pixelColor.graya(160, 255))
  second:drawPixel(1, 0, app.pixelColor.graya(240, 255))
else
  local palette = sprite.palettes[1]
  palette:resize(8)
  palette:setColor(1, Color { r = 255, g = 0, b = 0, a = 255 })
  palette:setColor(3, Color { r = 0, g = 0, b = 255, a = 255 })
  local unsafe = app.params.unsafe == "true"
  sprite.transparentColor = unsafe and 7 or 0
  first:clear(sprite.transparentColor)
  first:drawPixel(0, 0, unsafe and 3 or 1)
  second = Image(first)
end
sprite:newEmptyFrame()
sprite:newCel(layer, 2, second)
if mode == ColorMode.RGB then
  local hidden = sprite:newLayer()
  local image = Image(3, 1, mode)
  image:clear(app.pixelColor.rgba(123, 7, 222, 255))
  sprite:newCel(hidden, 1, image)
  hidden.isVisible = false
end
assert(sprite:saveAs(app.params.source))
sprite:close()
