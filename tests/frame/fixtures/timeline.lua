local sprite = Sprite(3, 2, ColorMode.RGB)
local layer = sprite.layers[1]
local durations = { 120, 300, 400, 500 }
for number = 2, 4 do
  sprite:newEmptyFrame(number)
end
for number = 1, 4 do
  sprite.frames[number].duration = durations[number] / 1000
  local cel = layer:cel(number)
  if cel == nil then cel = sprite:newCel(layer, number, Image(3, 2, ColorMode.RGB)) end
  cel.image:putPixel(0, 0, app.pixelColor.rgba(number * 30, 0, 0, 255))
end
local tag = sprite:newTag(2, 3)
tag.name = "middle"
local slice = sprite:newSlice(Rectangle(0, 0, 1, 1))
slice.name = "mark"
assert(sprite:saveAs(app.params.out))
sprite:close()
