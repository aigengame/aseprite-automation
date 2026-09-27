local mode = app.params.mode or "rgb"
local color_mode = mode == "grayscale" and ColorMode.GRAY
  or mode == "indexed" and ColorMode.INDEXED
  or ColorMode.RGB
local sprite = Sprite(4, 3, color_mode)
local layer = sprite.layers[1]
layer.name = "Stored"
local image = layer:cel(1).image
if color_mode == ColorMode.RGB then
  image:clear(app.pixelColor.rgba(10, 20, 30, 255))
  image:putPixel(1, 1, app.pixelColor.rgba(70, 80, 90, 0))
  image:putPixel(2, 1, app.pixelColor.rgba(3, 4, 5, 128))
elseif color_mode == ColorMode.GRAY then
  image:clear(app.pixelColor.graya(42, 255))
  image:putPixel(1, 1, app.pixelColor.graya(72, 0))
  image:putPixel(2, 1, app.pixelColor.graya(9, 128))
else
  local palette = Palette(4)
  palette:setColor(0, Color { r = 30, g = 40, b = 50, a = 255 })
  palette:setColor(1, Color { r = 250, g = 0, b = 0, a = 255 })
  palette:setColor(2, Color { r = 0, g = 0, b = 250, a = 255 })
  palette:setColor(3, Color { r = 0, g = 250, b = 0, a = 255 })
  sprite:setPalette(palette)
  sprite.transparentColor = 2
  image:clear(1)
  image:putPixel(1, 1, 0)
  image:putPixel(2, 1, 2)
end
layer.isVisible = false
layer:cel(1).opacity = 0
assert(sprite:saveAs(app.params.out))
sprite:close()
