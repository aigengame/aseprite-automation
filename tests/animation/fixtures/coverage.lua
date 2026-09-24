local sprite = Sprite(3, 2, ColorMode.RGB)
local base = sprite.layers[1]
base.name = "base"
local upper = sprite:newLayer()
upper.name = "upper"

local function dot(layer, frame, x)
  local image = Image(1, 1, ColorMode.RGB)
  image:putPixel(0, 0, app.pixelColor.rgba(200, 40, 80, 255))
  sprite:newCel(layer, frame, image, Point(x, 0))
end

dot(base, 1, 0)
dot(upper, 1, 1)
sprite.frames[1].duration = 0.1
sprite:newEmptyFrame()
dot(base, 2, 0)
dot(upper, 2, 0)
sprite.frames[2].duration = 0.2
sprite:newEmptyFrame()
dot(upper, 3, 2)
sprite.frames[3].duration = 0.3
assert(sprite:saveAs(app.params.out))
sprite:close()
