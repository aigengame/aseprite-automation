local sprite = Sprite(4, 4, ColorMode.RGB)
sprite.useLayerUuids = true

local lower = sprite.layers[1]
lower.name = "lower"
lower:cel(1).image:putPixel(0, 0, app.pixelColor.rgba(0, 0, 255, 255))

local upper = sprite:newLayer()
upper.name = "upper"
local red = Image(4, 4, ColorMode.RGB)
red:putPixel(0, 0, app.pixelColor.rgba(255, 0, 0, 200))
sprite:newCel(upper, 1, red)

local group = sprite:newGroup()
group.name = "group"
local child = sprite:newLayer()
child.name = "child"
child.parent = group
local green = Image(4, 4, ColorMode.RGB)
green:putPixel(1, 1, app.pixelColor.rgba(0, 255, 0, 255))
sprite:newCel(child, 1, green)

sprite:newEmptyFrame(2)
local yellow = Image(4, 4, ColorMode.RGB)
yellow:putPixel(2, 2, app.pixelColor.rgba(255, 255, 0, 255))
sprite:newCel(upper, 2, yellow)

assert(sprite:saveAs(app.params.out))
sprite:close()
