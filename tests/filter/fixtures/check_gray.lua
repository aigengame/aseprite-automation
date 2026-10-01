local sprite = app.open(app.params.source)
local image = sprite.cels[1].image
assert(image:getPixel(0, 0) == app.pixelColor.graya(150, 255))
assert(image:getPixel(1, 0) == app.pixelColor.graya(255, 128))
assert(image:getPixel(2, 0) == app.pixelColor.graya(60, 255))
sprite:close()
