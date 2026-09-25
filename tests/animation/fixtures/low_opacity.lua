local sprite = Sprite(1, 1, ColorMode.RGB)
local first = sprite.layers[1]
first.name = "first"
local second = sprite:newLayer()
second.name = "second"
local image = Image(1, 1, ColorMode.RGB)
image:putPixel(0, 0, app.pixelColor.rgba(20, 30, 40, 255))
sprite:newCel(second, 1, image)
first:cel(1).image:putPixel(0, 0, app.pixelColor.rgba(20, 30, 40, 255))
first.opacity = 1
first:cel(1).opacity = 1
second.opacity = 1
second:cel(1).opacity = 1
assert(sprite:saveAs(app.params.out))
sprite:close()
