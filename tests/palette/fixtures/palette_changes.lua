-- A multi-frame document; tests inject additional Palette chunks as fixture data.
local mode = ({ rgb = ColorMode.RGB, grayscale = ColorMode.GRAY, indexed = ColorMode.INDEXED })[app.params.mode]
local sprite = Sprite(3, 1, mode)
local palette = sprite.palettes[1]
palette:resize(4)
palette:setColor(0, Color { r = 10, g = 20, b = 30, a = 255 })
palette:setColor(1, Color { r = 240, g = 40, b = 60, a = 255 })
palette:setColor(2, Color { r = 20, g = 200, b = 40, a = 128 })
palette:setColor(3, Color { r = 50, g = 60, b = 70, a = 0 })
sprite.transparentColor = 3
local image = sprite.cels[1].image
if mode == ColorMode.INDEXED then
  image:drawPixel(0, 0, 1)
  image:drawPixel(1, 0, 3)
  image:drawPixel(2, 0, 2)
end
for frame = 2, 5 do
  sprite:newEmptyFrame()
  sprite:newCel(sprite.layers[1], frame, image, Point(0, 0))
end
assert(sprite:saveAs(app.params.source))
sprite:close()
