local sprite = Sprite(4, 4, ColorMode.RGB)
local group = sprite:newGroup()
group.name = "group"

local lower = sprite:newLayer()
lower.name = "nested-lower"
lower.parent = group
local lower_image = Image(4, 4, ColorMode.RGB)
lower_image:putPixel(1, 1, app.pixelColor.rgba(0, 0, 255, 255))
sprite:newCel(lower, 1, lower_image)

local upper = sprite:newLayer()
upper.name = "nested-upper"
upper.parent = group
local upper_image = Image(4, 4, ColorMode.RGB)
upper_image:putPixel(1, 1, app.pixelColor.rgba(255, 0, 0, 128))
sprite:newCel(upper, 1, upper_image)

assert(sprite:saveAs(app.params.out))
sprite:close()
