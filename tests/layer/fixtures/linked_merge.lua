local sprite = Sprite(4, 4, ColorMode.RGB)
local lower = sprite.layers[1]
lower.name = "lower"
lower:cel(1).image:putPixel(0, 0, app.pixelColor.rgba(0, 0, 255, 255))
app.activeSprite = sprite
app.activeLayer = lower
app.activeFrame = sprite.frames[1]
assert(app.command.NewFrame { content = "cellinked" })
assert(lower:cel(1).image == lower:cel(2).image)

local upper = sprite:newLayer()
upper.name = "upper"
local transparent = Image(4, 4, ColorMode.RGB)
sprite:newCel(upper, 1, transparent)
assert(sprite:saveAs(app.params.out))
sprite:close()
