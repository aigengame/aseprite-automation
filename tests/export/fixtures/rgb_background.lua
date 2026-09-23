local sprite = Sprite(2, 1, ColorMode.RGB)
local image = sprite.layers[1].cels[1].image
image:putPixel(0, 0, app.pixelColor.rgba(10, 20, 30, 255))
image:putPixel(1, 0, app.pixelColor.rgba(40, 50, 60, 255))
app.activeSprite = sprite
app.activeLayer = sprite.layers[1]
app.activeFrame = sprite.frames[1]
app.bgColor = Color { r = 0, g = 0, b = 0, a = 255 }
app.command.BackgroundFromLayer()
assert(sprite.layers[1].isBackground)
assert(sprite:saveAs(app.params.out))
sprite:close()
