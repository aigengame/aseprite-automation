local modes = { rgb = ColorMode.RGB, grayscale = ColorMode.GRAY, indexed = ColorMode.INDEXED }
local sprite = Sprite(3, 1, modes[app.params.mode])
sprite.layers[1].name = "Ink"
local palette = Palette(4)
palette:setColor(0, Color { r = 0, g = 0, b = 0, a = 0 })
palette:setColor(1, Color { r = 100, g = 60, b = 20, a = 255 })
palette:setColor(2, Color { r = 150, g = 90, b = 30, a = 255 })
palette:setColor(3, Color { r = 200, g = 120, b = 40, a = 255 })
sprite:setPalette(palette)
local image = sprite.cels[1].image
if sprite.colorMode == ColorMode.RGB then
  image:drawPixel(0, 0, app.pixelColor.rgba(100, 60, 20, 255))
  image:drawPixel(1, 0, app.pixelColor.rgba(200, 100, 40, 128))
  image:drawPixel(2, 0, app.pixelColor.rgba(40, 20, 10, 255))
elseif sprite.colorMode == ColorMode.GRAY then
  image:drawPixel(0, 0, app.pixelColor.graya(100, 255))
  image:drawPixel(1, 0, app.pixelColor.graya(200, 128))
  image:drawPixel(2, 0, app.pixelColor.graya(40, 255))
else
  image:drawPixel(0, 0, 1)
  image:drawPixel(1, 0, 2)
  image:drawPixel(2, 0, 3)
end
sprite:saveAs(app.params.source)
sprite:close()
