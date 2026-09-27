local sprite = Sprite(4, 4, ColorMode.RGB)
sprite.layers[1].name = "subject"
sprite.layers[1].opacity = 128
local cel = sprite.layers[1]:cel(1)
local image = Image(2, 2, ColorMode.RGB)
image:putPixel(1, 0, app.pixelColor.rgba(255, 0, 0, 128))
cel.image = image
cel.position = Point(-1, 1)
cel.opacity = 128
sprite:newEmptyFrame(2)
assert(sprite:saveAs(app.params.out))
sprite:close()
