local sprite = assert(app.open(app.params.source))
local layer = assert(sprite.layers[1])
assert(layer.isBackground)
local mode = app.params.mode
local expected = mode == "grayscale" and app.pixelColor.graya(60, 255) or 2
for number = 1, #sprite.frames do
  local cel = assert(layer:cel(number))
  assert(cel.image:getPixel(0, 0) == expected, "Background fill differs on Frame " .. number)
end
sprite:close()
