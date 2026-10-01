local sprite = app.open(app.params.source)
local pal = sprite.palettes[1]
assert(pal:getColor(1).red == 150)
assert(pal:getColor(1).green == 60)
assert(pal:getColor(1).blue == 20)
assert(pal:getColor(1).alpha == 255)
assert(pal:getColor(2).red == 150)
local image = sprite.cels[1].image
if app.params.mode == "indexed" then
  assert(image:getPixel(0, 0) == 1 and image:getPixel(1, 0) == 2 and image:getPixel(2, 0) == 3)
else
  assert(image:getPixel(0, 0) == app.pixelColor.rgba(150, 60, 20, 255))
  assert(image:getPixel(1, 0) == app.pixelColor.rgba(200, 100, 40, 128))
  assert(image:getPixel(2, 0) == app.pixelColor.rgba(40, 20, 10, 255))
end
sprite:close()
