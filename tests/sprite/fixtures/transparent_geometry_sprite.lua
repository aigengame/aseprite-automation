local sprite = Sprite(4, 4, ColorMode.RGB)
local layer = sprite.layers[1]
if layer:cel(1) then sprite:deleteCel(layer, 1) end
local transparent = Image(2, 2, ColorMode.RGB)
sprite:newCel(layer, 1, transparent, Point(1, 1))
assert(sprite:saveAs(app.params.out))
sprite:close()
