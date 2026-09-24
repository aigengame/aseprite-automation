local sprite = Sprite(3, 2, ColorMode.RGB)
sprite.useLayerUuids = true
sprite:newEmptyFrame()
local effects = sprite:newLayer()
effects.name = "effects"
local red = Image(1, 1, ColorMode.RGB)
red:drawPixel(0, 0, app.pixelColor.rgba(255, 0, 0, 255))
sprite:newCel(effects, 1, red, Point(1, 0))
local blue = Image(1, 1, ColorMode.RGB)
blue:drawPixel(0, 0, app.pixelColor.rgba(0, 0, 255, 255))
sprite:newCel(effects, 2, blue, Point(1, 1))
local tag = sprite:newTag(1, 2)
tag.name = "action"
local slice = sprite:newSlice(Rectangle(0, 0, 2, 2))
slice.name = "focus"
assert(sprite:saveAs(app.params.out))
sprite:close()
