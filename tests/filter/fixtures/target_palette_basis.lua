local mode = app.params.mode
local color_mode = mode == "indexed" and ColorMode.INDEXED or ColorMode.RGB
local sprite = Sprite(1, 1, color_mode)
local palette = Palette(mode == "indexed" and 3 or 2)
palette:setColor(0, Color { r = 0, g = 0, b = 0, a = 0 })
palette:setColor(1, Color { r = 80, g = 0, b = 0, a = 255 })
if mode == "indexed" then
  palette:setColor(2, Color { r = 120, g = 0, b = 0, a = 255 })
  sprite.transparentColor = 0
end
sprite:setPalette(palette)
local layer = sprite.layers[1]
layer.name = "Basis"
local source_pixel = mode == "indexed" and 1 or app.pixelColor.rgba(20, 0, 0, 255)
layer:cel(1).image:drawPixel(0, 0, source_pixel)
sprite:newEmptyFrame()
local anchor = Image(1, 1, color_mode)
anchor:drawPixel(0, 0, source_pixel)
sprite:newCel(layer, 2, anchor, Point(0, 0))
assert(sprite:saveAs(app.params.source))
sprite:close()
