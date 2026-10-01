-- Native Matrix loading samples the canvas-sized region of the first Cel Image.
local width, height = tonumber(app.params.image_width), tonumber(app.params.image_height)
local sprite = Sprite(2, 2, ColorMode.INDEXED)
local image = Image(width, height, ColorMode.INDEXED)
image:clear(3)
local ranks = { { 0, 2 }, { 3, 1 } }
for y = 0, math.min(height, 2) - 1 do
  for x = 0, math.min(width, 2) - 1 do
    image:drawPixel(x, y, ranks[y + 1][x + 1])
  end
end
sprite.cels[1].image = image
assert(sprite:saveAs(app.params.target))
sprite:close()
sprite = assert(app.open(app.params.target))
assert(sprite.width == 2 and sprite.height == 2)
assert(sprite.cels[1].image.width == width and sprite.cels[1].image.height == height)
sprite:close()
