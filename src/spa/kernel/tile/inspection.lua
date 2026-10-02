-- Tile-owned native identities, bindings, and placement observations.
local module = {}
local layers = dofile(app.params.layer_select)

local function grid(value)
  return {
    origin = { x = value.origin.x, y = value.origin.y },
    tile_size = { width = value.tileSize.width, height = value.tileSize.height },
  }
end

local function bindings(sprite, tileset)
  local result = {}
  local function visit(items)
    for _, layer in ipairs(items) do
      if layer.isTilemap and layer.tileset == tileset then
        result[#result + 1] = { layer_path = layers.current_path(sprite, layer), name = layer.name }
      elseif layer.isGroup then
        visit(layer.layers)
      end
    end
  end
  visit(sprite.layers)
  return result
end

local function facts(sprite, tileset, index)
  return {
    tileset_index = index, name = tileset.name, base_index = tileset.baseIndex,
    tile_count = #tileset, grid = grid(tileset.grid), layers = bindings(sprite, tileset),
  }
end

function module.read(sprite, payload)
  local result = { status = "success", operation = "spa " .. payload.operation, sprite_file = payload.sprite_file, complete = true, tilesets = {} }
  for index, tileset in ipairs(sprite.tilesets) do result.tilesets[#result.tilesets + 1] = facts(sprite, tileset, index) end
  return result
end

return module
