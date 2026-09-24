local sprite = Sprite(4, 4, ColorMode.RGB)
sprite.gridBounds = Rectangle(1, 1, 2, 2)
sprite:newEmptyFrame(2)
local layer = sprite.layers[1]
if layer:cel(1) then sprite:deleteCel(layer, 1) end
local image = Image(2, 2, ColorMode.RGB)
image:drawPixel(0, 0, app.pixelColor.rgba(255, 0, 0, 255))
image:drawPixel(1, 1, app.pixelColor.rgba(0, 0, 255, 255))
sprite:newCel(layer, 1, image, Point(1, 1))
local outside = Image(3, 2, ColorMode.RGB)
outside:drawPixel(2, 0, app.pixelColor.rgba(0, 255, 0, 255))
sprite:newCel(layer, 2, outside, Point(-1, 2))
local tag = sprite:newTag(1, 2)
tag.name = "loop"
local slice = sprite:newSlice(Rectangle(1, 1, 2, 2))
slice.name = "region"
assert(sprite:saveAs(app.params.out))
sprite:close()
