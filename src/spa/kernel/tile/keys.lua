-- One native Tile Key projection and exact lookup for inspection and authoring.
local module = {}
local properties = dofile(app.params.tile_properties)
local null = json.decode("null")

function module.observe(tile)
  if tile == nil or tile.index == 0 then return null end
  local value = properties.observe(tile.properties("aigengame.spa").tile_key)
  if value.kind == "nil" then return null, "tile_key_missing" end
  if value.kind ~= "string" or #value.value == 0 then return null, "tile_key_invalid" end
  return value.value
end

function module.resolve(tileset, key)
  local found
  for index = 1, #tileset - 1 do
    if module.observe(tileset:tile(index)) == key then
      if found then
        return nil,
          {
            rejection = {
              code = "tile_key_ambiguous",
              message = "Tile Key is duplicated within the Tileset",
            },
          }
      end
      found = index
    end
  end
  if not found then
    return nil, { rejection = { code = "tile_key_missing", message = "No Tile has this Tile Key" } }
  end
  return found
end

return module
