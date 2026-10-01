local sprite = assert(app.open(app.params.source))
local function pixels(image)
  local result = {}
  for pixel in image:pixels() do
    result[#result + 1] = pixel()
  end
  return result
end
local result = { cels = {}, tiles = {}, palette = {} }
for _, cel in ipairs(sprite.cels) do
  result.cels[#result.cels + 1] = {
    layer = cel.layer.name,
    frame = cel.frameNumber,
    x = cel.position.x,
    y = cel.position.y,
    width = cel.image.width,
    height = cel.image.height,
    pixels = pixels(cel.image),
  }
end
for _, tileset in ipairs(sprite.tilesets) do
  for index = 0, #tileset - 1 do
    local tile = tileset:tile(index)
    result.tiles[#result.tiles + 1] =
      { index = index, pixels = pixels(tile.image), data = tile.data }
  end
end
for index = 0, #sprite.palettes[1] - 1 do
  local color = sprite.palettes[1]:getColor(index)
  result.palette[#result.palette + 1] = { color.red, color.green, color.blue, color.alpha }
end
local file = assert(io.open(app.params.response, "wb"))
file:write(json.encode(result))
file:close()
sprite:close()
