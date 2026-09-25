local sprite = Sprite(4, 4, ColorMode.RGB)
local source = sprite.layers[1]
source.name = "Source"
local other = sprite:newLayer()
other.name = "Other"
sprite:newEmptyFrame(2)
sprite:newEmptyFrame(3)
sprite:newEmptyFrame(4)
for number, frame in ipairs(sprite.frames) do
  frame.duration = number / 10
end
local tag = sprite:newTag(2, 3)
tag.name = "action"
local image = Image(2, 2, ColorMode.RGB)
image:drawPixel(0, 0, Color { r = 30, g = 40, b = 50, a = 255 })
local cel = sprite:newCel(source, 1, image, Point(1, 1))
cel.opacity = 210
cel.zIndex = 2
assert(sprite:saveAs(app.params.out))
sprite:close()
