-- Layer-owned exact target selection against one open Sprite.
local module = {}

local function find_by_value(layers, prefix, predicate, found)
  for index = 1, #layers do
    local layer = layers[index]
    local path = {}
    for _, item in ipairs(prefix) do
      path[#path + 1] = item
    end
    path[#path + 1] = index
    if predicate(layer) then found[#found + 1] = { layer = layer, path = path } end
    if layer.isGroup then find_by_value(layer.layers, path, predicate, found) end
  end
end

function module.resolve(sprite, address)
  if address.layer_path ~= nil then
    local siblings = sprite.layers
    local layer = nil
    for depth, index in ipairs(address.layer_path) do
      if type(index) ~= "number" or index % 1 ~= 0 or index < 1 or index > #siblings then
        return nil, "layer_invalid_path", "Layer path is outside the current hierarchy"
      end
      layer = siblings[index]
      if depth < #address.layer_path and not layer.isGroup then
        return nil, "layer_invalid_path", "Layer path traverses a non-Group Layer"
      end
      if layer.isGroup then siblings = layer.layers end
    end
    local path = {}
    for _, index in ipairs(address.layer_path) do
      path[#path + 1] = index
    end
    return { layer = layer, path = path }
  end
  if address.layer_uuid ~= nil and not sprite.useLayerUuids then
    return nil, "layer_uuid_unpersisted", "Sprite does not persist Layer UUIDs"
  end
  local matches = {}
  if address.layer_uuid ~= nil then
    find_by_value(
      sprite.layers,
      {},
      function(layer) return tostring(layer.uuid) == address.layer_uuid end,
      matches
    )
  else
    find_by_value(
      sprite.layers,
      {},
      function(layer) return layer.name == address.layer_name end,
      matches
    )
  end
  if #matches == 0 then return nil, "layer_missing", "No Layer matches the address" end
  if #matches > 1 then
    return nil, "layer_ambiguous", "Layer name matches more than one Layer in the Sprite"
  end
  return matches[1]
end

return module
