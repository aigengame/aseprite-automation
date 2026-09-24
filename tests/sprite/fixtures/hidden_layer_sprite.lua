local sprite = Sprite(2, 2, ColorMode.RGB)
local base = sprite.layers[1]
base.name = "blue"
local blue = Image(2, 2, ColorMode.RGB)
blue:drawPixel(0, 0, app.pixelColor.rgba(0, 0, 255, 255))
sprite:newCel(base, 1, blue, Point(0, 0))
local hidden = sprite:newLayer()
hidden.name = "hidden red"
local red = Image(2, 2, ColorMode.RGB)
red:drawPixel(0, 0, app.pixelColor.rgba(255, 0, 0, 255))
sprite:newCel(hidden, 1, red, Point(0, 0))
hidden.isVisible = false
assert(sprite:saveAs(app.params.out))
sprite:close()
