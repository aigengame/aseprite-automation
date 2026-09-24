local sprite = Sprite(2, 1, ColorMode.RGB)
local lower = sprite.layers[1]
lower.name = "lower"
lower:cel(1).image:putPixel(0, 0, app.pixelColor.rgba(200, 20, 10, 128))
lower:cel(1).image:putPixel(1, 0, app.pixelColor.rgba(10, 40, 220, 255))

local upper = sprite:newLayer()
upper.name = "upper"
upper.opacity = 190
upper.blendMode = BlendMode.MULTIPLY
local image = Image(2, 1, ColorMode.RGB)
image:putPixel(0, 0, app.pixelColor.rgba(20, 200, 40, 180))
image:putPixel(1, 0, app.pixelColor.rgba(230, 160, 80, 128))
sprite:newCel(upper, 1, image)

assert(sprite:saveAs(app.params.out))
sprite:close()
