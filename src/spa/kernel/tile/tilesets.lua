-- Shared exact Tileset resolution, native Grid facts, and Layer bindings.
local module = {}
local layers = dofile(app.params.layer_select)
local null = json.decode("null")
local function reject(code, message) return { rejection = { code = code, message = message } } end

local function integer(value, minimum, maximum)
  local n = tonumber(value)
  if n == nil or n % 1 ~= 0 or n < minimum or n > maximum then return nil end
  return math.tointeger(n)
end

local function grid(value)
  return {
    origin = { x = value.origin.x, y = value.origin.y },
    tile_size = { width = value.tileSize.width, height = value.tileSize.height },
  }
end

local function layer_facts(sprite, layer, uuids)
  local path = layers.current_path(sprite, layer)
  return {
    layer_path = path,
    layer_uuid = uuids[table.concat(path, "/")] or null,
    name = layer.name,
  }
end

local function tilemap_layers(sprite)
  local result = {}
  local function visit(items)
    for _, layer in ipairs(items) do
      if layer.isTilemap then
        result[#result + 1] = layer
      elseif layer.isGroup then
        visit(layer.layers)
      end
    end
  end
  visit(sprite.layers)
  return result
end

local function bindings(sprite, tileset, uuids)
  local result = {}
  for _, layer in ipairs(tilemap_layers(sprite)) do
    if layer.tileset == tileset then result[#result + 1] = layer_facts(sprite, layer, uuids) end
  end
  return result
end

local function facts(sprite, tileset, index, uuids)
  return {
    tileset_index = index,
    name = tileset.name,
    base_index = tileset.baseIndex,
    tile_count = #tileset,
    grid = grid(tileset.grid),
    layers = bindings(sprite, tileset, uuids),
  }
end

local function resolve_layer(sprite, address, uuids)
  if address.layer_path then
    local normalized = {}
    for _, item in ipairs(address.layer_path) do
      normalized[#normalized + 1] = tonumber(item) or -1
    end
    address = { layer_path = normalized }
  end
  local selected, code, message = layers.resolve(sprite, address, uuids)
  if not selected then return nil, reject(code, message) end
  if not selected.layer.isTilemap then
    return nil, reject("tilemap_layer_required", "Select an exact Tilemap Layer")
  end
  return selected.layer
end

local function tileset_index(sprite, tileset)
  for index, item in ipairs(sprite.tilesets) do
    if item == tileset then return index end
  end
end

local function resolve_tileset(sprite, target, uuids)
  if target.layer then
    local layer, failure = resolve_layer(sprite, target.layer, uuids)
    if failure then return nil, nil, failure end
    local index = tileset_index(sprite, layer.tileset)
    if index then return layer.tileset, index end
  elseif target.tileset_index then
    local index = integer(target.tileset_index, 1, #sprite.tilesets)
    if index then return sprite.tilesets[index], index end
  else
    local found, found_index
    for index, item in ipairs(sprite.tilesets) do
      if item.name == target.tileset_name then
        if found then
          return nil, nil, reject("tileset_ambiguous", "Tileset name must match exactly once")
        end
        found, found_index = item, index
      end
    end
    if found then return found, found_index end
  end
  return nil, nil, reject("tileset_missing", "No Tileset matches the current address or binding")
end

module.grid = grid
module.layer_facts = layer_facts
module.tilemap_layers = tilemap_layers
module.facts = facts
module.resolve_layer = resolve_layer
module.tileset_index = tileset_index
module.resolve_tileset = resolve_tileset

return module
