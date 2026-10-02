local sprite = Sprite(4, 1, ColorMode.RGB)
local image = Image(1, 1, ColorMode.RGB)
image:drawPixel(0, 0, app.pixelColor.rgba(0, 0, 255, 255))
local cel = sprite.cels[1]
cel.image = image
cel.position = Point(1, 0)
if app.params.linked == "true" then app.command.NewFrame { content = "cellinked" } end
assert(sprite:saveAs(app.params.source))
sprite:close()
