local sprite = app.open(app.params.source)
local image = sprite.cels[1].image
assert(image:getPixel(0, 0) == app.pixelColor.rgba(150, 90, 30, 255))
assert(image:getPixel(1, 0) == app.pixelColor.rgba(255, 150, 60, 128))
assert(image:getPixel(2, 0) == app.pixelColor.rgba(60, 30, 15, 255))
sprite:close()
