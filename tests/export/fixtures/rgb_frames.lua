local sprite = Sprite(3, 2, ColorMode.RGB)
local first = sprite.layers[1].cels[1].image
first:putPixel(0, 0, app.pixelColor.rgba(200, 10, 20, 255))
sprite:newEmptyFrame()
local second = Image(3, 2, ColorMode.RGB)
second:putPixel(1, 0, app.pixelColor.rgba(17, 34, 51, 128))
sprite:newCel(sprite.layers[1], 2, second)
local hidden = sprite:newLayer()
hidden.name = "hidden"
hidden.isVisible = false
local hidden_image = Image(3, 2, ColorMode.RGB)
hidden_image:putPixel(1, 0, app.pixelColor.rgba(255, 0, 0, 255))
sprite:newCel(hidden, 2, hidden_image)
assert(sprite:saveAs(app.params.out))
sprite:close()
