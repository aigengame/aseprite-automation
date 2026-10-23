-- Independent Cel oracle; no SPA Kernel module is loaded.
-- Write the Layer path, Frame, position and raw bytes of each Cel and Tile.
local sprite = assert(app.open(app.params.source))
local null = json.decode("null")

local function hex(bytes)
  return (bytes:gsub(".", function(byte) return string.format("%02x", string.byte(byte)) end))
end

local function layer_path(layer)
  local numbers = {}
  while layer ~= sprite do
    table.insert(numbers, 1, layer.stackIndex)
    layer = layer.parent
  end
  return numbers
end

local cels = {}
for _, cel in ipairs(sprite.cels) do
  cels[#cels + 1] = {
    layer_path = layer_path(cel.layer),
    frame_number = cel.frameNumber,
    x = cel.position.x,
    y = cel.position.y,
    bytes = hex(cel.image.bytes),
  }
end
local tiles = {}
for number, tileset in ipairs(sprite.tilesets) do
  for index = 0, #tileset - 1 do
    local image = tileset:tile(index).image
    tiles[#tiles + 1] = {
      tileset_number = number,
      tile_index = index,
      bytes = image and hex(image.bytes) or null,
    }
  end
end
sprite:close()
local file = assert(io.open(app.params.response, "wb"))
file:write(json.encode({ cels = cels, tiles = tiles }))
file:close()
