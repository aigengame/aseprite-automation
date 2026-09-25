local sprite = Sprite(4, 4, ColorMode.RGB)
app.activeSprite = sprite
app.command.NewLayer { reference = true, ui = false }
local layer = app.activeLayer
assert(layer.isReference)
local image = Image(3, 3, ColorMode.RGB)
image:drawPixel(0, 0, app.pixelColor.rgba(255, 0, 0, 255))
sprite:newCel(layer, 1, image, Point(0, 0))
assert(sprite:saveAs(app.params.out))
sprite:close()
