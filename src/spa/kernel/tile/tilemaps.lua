-- Shared Tilemap Cel topology observations for reads and region writes.
local module = {}
local tilesets = dofile(app.params.tilesets)
local null = json.decode("null")

local function cel_facts(sprite, layer, frame, uuids)
  local result = {
    layer = tilesets.layer_facts(sprite, layer, uuids),
    tileset_index = assert(tilesets.tileset_index(sprite, layer.tileset)),
    frame_number = frame,
    exists = false,
    position = null,
    cell_size = null,
    effective_grid = null,
    canvas_coverage = null,
  }
  local cel = layer:cel(frame)
  if cel then
    local value = tilesets.grid(layer.tileset.grid)
    value.origin.x, value.origin.y =
      value.origin.x + cel.position.x, value.origin.y + cel.position.y
    result.exists = true
    result.position = { x = cel.position.x, y = cel.position.y }
    result.cell_size = { width = cel.image.width, height = cel.image.height }
    result.effective_grid = value
    result.canvas_coverage = {
      x = value.origin.x,
      y = value.origin.y,
      width = cel.image.width * value.tile_size.width,
      height = cel.image.height * value.tile_size.height,
    }
  end
  return result
end

module.cel_facts = cel_facts
return module
