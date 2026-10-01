local sprite = app.open(app.params.source)
local image = sprite.cels[1].image
assert(image:getPixel(0, 0) == 2)
assert(image:getPixel(1, 0) == 3)
assert(image:getPixel(2, 0) == 3)
assert(sprite.palettes[1]:getColor(1).red == 100)
sprite:close()
