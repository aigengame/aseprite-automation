-- Tile-owned geometry, Empty Tile construction, and creation observations.
local module = {}
local inspection = dofile(app.params.tile_inspection)

local function reject(message)
  return { rejection = { code = "cel_unsupported_target", message = message } }
end

function module.observe(sprite, layer, frame, uuids)
  local cel = assert(layer:cel(frame), "created Tilemap Cel is absent")
  assert(cel.image.colorMode == ColorMode.TILEMAP, "created Image is not a Tilemap")
  for value in cel.image:pixels() do
    assert(value() == 0, "created Tilemap Cell is not Empty Tile 0 without flags")
  end
  local index = assert(inspection.tileset_index(sprite, layer.tileset))
  return {
    tilemap = inspection.cel_facts(sprite, layer, frame, uuids),
    tileset = inspection.tileset_facts(sprite, layer.tileset, index, uuids),
    empty_tile_cells_verified = true,
  }
end

function module.add(sprite, layer, frame, input, uuids)
  local size = input.tilemap_size
  if size == nil or input.image_size ~= nil then
    return reject("Tilemap Cel add requires tilemap_size in Tile Cells and no image_size")
  end
  local width, height = size.width, size.height
  if
    type(width) ~= "number"
    or type(height) ~= "number"
    or width % 1 ~= 0
    or height % 1 ~= 0
    or width < 1
    or height < 1
    or width > 65535
    or height > 65535
    or width * height > 1048576
  then
    return reject("Tilemap size requires sides 1..65535 and at most 1048576 Tile Cells")
  end
  if not inspection.tileset_index(sprite, layer.tileset) then
    return reject("Tilemap Cel add requires an existing Tileset binding")
  end
  local grid = layer.tileset.grid
  local w, h = width * grid.tileSize.width, height * grid.tileSize.height
  if
    grid.tileSize.width < 1
    or grid.tileSize.height < 1
    or w > 2147483647
    or h > 2147483647
    or grid.origin.x + w > 2147483647
    or grid.origin.y + h > 2147483647
  then
    return reject("Tilemap Canvas coverage must fit native signed 32-bit Rectangle coordinates")
  end
  app.transaction("Add Tilemap Cel", function()
    local image = Image(width, height, ColorMode.TILEMAP)
    image:clear(0)
    local created = sprite:newCel(layer, frame, image, Point(0, 0))
    assert(created.image.width == width and created.image.height == height, "Tilemap size narrowed")
  end)
  return module.observe(sprite, layer, frame, uuids)
end

return module
