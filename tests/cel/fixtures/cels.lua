local sprite = Sprite(4, 3, ColorMode.RGB)
local layer = sprite.layers[1]
if layer:cel(1) then sprite:deleteCel(layer, 1) end
sprite:newEmptyFrame(2)
sprite:newEmptyFrame(3)
local empty = Image(2, 2, ColorMode.RGB)
sprite:newCel(layer, 2, empty, Point(1, 0))
local colored = Image(1, 1, ColorMode.RGB)
colored:drawPixel(0, 0, Color { r = 30, g = 40, b = 50, a = 255 })
sprite:newCel(layer, 3, colored, Point(2, 1))
assert(sprite:saveAs(app.params.out))
sprite:close()
