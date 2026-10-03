-- Native Tile identities, exact bindings, complete regions, and validation.
local module = {}
local layers = dofile(app.params.layer_select)
local sprites = dofile(app.params.inspection)
local pixels = dofile(app.params.image_snapshot)
local properties = dofile(app.params.tile_properties)
local null = json.decode("null")

local function reject(code, message) return { rejection = { code = code, message = message } } end

local function snapshot_limit(unit, requested, maximum)
  local result = reject(
    "tile_snapshot_destination_required",
    "Snapshot exceeds the inline limit; provide snapshot_destination"
  )
  result.rejection.snapshot_limit = { unit = unit, requested = requested, maximum_inline = maximum }
  return result
end

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

local function tile_key(tile)
  if tile == nil or tile.index == 0 then return null end
  local value = tile.properties("aigengame.spa").tile_key
  if type(value) == "string" and #value > 0 then return value end
  return null
end

local function tile_facts(tileset, tile, namespaces)
  local color = tile.color
  return {
    tile_index = tile.index,
    tile_key = tile_key(tile),
    display_index = tile.index + tileset.baseIndex - 1,
    image_size = { width = tile.image.width, height = tile.image.height },
    color_mode = pixels.mode(tile.image),
    data = tile.data,
    color = { red = color.red, green = color.green, blue = color.blue, alpha = color.alpha },
    properties = properties.read(tile, namespaces),
  }
end

local function resolve_tile(tileset, address)
  if address.tile_index then
    local index = integer(address.tile_index, 0, #tileset - 1)
    if index then return tileset:tile(index) end
    return nil, reject("tile_index_out_of_bounds", "Tile index is outside the current Tileset")
  end
  local found
  for index = 1, #tileset - 1 do
    local tile = tileset:tile(index)
    if tile_key(tile) == address.tile_key then
      if found then
        return nil, reject("tile_key_ambiguous", "Tile Key is duplicated within the Tileset")
      end
      found = tile
    end
  end
  if not found then return nil, reject("tile_key_missing", "No Tile has this Tile Key") end
  return found
end

local function cel_facts(sprite, layer, frame, uuids)
  local result = {
    layer = layer_facts(sprite, layer, uuids),
    tileset_index = assert(tileset_index(sprite, layer.tileset)),
    frame_number = frame,
    exists = false,
    position = null,
    cell_size = null,
    effective_grid = null,
    canvas_coverage = null,
  }
  local cel = layer:cel(frame)
  if cel then
    local value = grid(layer.tileset.grid)
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

local function region(image, tileset, area)
  local result = {
    coordinate_space = "tile-cell",
    rectangle = area,
    complete = true,
    default = { kind = "empty" },
    entries = {},
  }
  local pc = app.pixelColor
  for y = area.y, area.y + area.height - 1 do
    for x = area.x, area.x + area.width - 1 do
      local packed = image:getPixel(x, y)
      local index, flags = pc.tileI(packed), pc.tileF(packed)
      if packed ~= 0 then
        result.entries[#result.entries + 1] = {
          tile_x = x,
          tile_y = y,
          placement = {
            kind = "tile",
            tile_index = index,
            tile_key = tile_key(tileset:tile(index)),
            flip_x = (flags & pc.TILE_XFLIP) ~= 0,
            flip_y = (flags & pc.TILE_YFLIP) ~= 0,
            flip_diagonal = (flags & pc.TILE_DFLIP) ~= 0,
          },
        }
      end
    end
  end
  return result
end

local function snapshot_output(result, value, payload)
  if payload.staged_snapshot_file then
    local file = assert(io.open(payload.staged_snapshot_file, "wb"))
    file:write(json.encode(value))
    file:close()
    result.snapshot, result.output_form = null, "artifact"
  else
    result.snapshot, result.output_form = value, "inline"
  end
  return result
end

local function key_findings(tileset, tsi)
  local result, seen = {}, {}
  for index = 0, #tileset - 1 do
    local tile = tileset:tile(index)
    local key, code
    -- Tile 0 has no SPA identity; its native Properties view can alias Tileset data.
    if index > 0 then
      key = tile.properties("aigengame.spa").tile_key
      if key == nil then
        code = "tile_key_missing"
      elseif type(key) ~= "string" or #key == 0 then
        code = "tile_key_invalid"
      elseif seen[key] then
        code = "tile_key_duplicate"
      else
        seen[key] = index
      end
    end
    if code then
      result[#result + 1] = {
        code = code,
        tileset_index = tsi,
        tile_index = index,
        tile_key = type(key) == "string" and key or null,
      }
    end
    if
      tile.image.width ~= tileset.grid.tileSize.width
      or tile.image.height ~= tileset.grid.tileSize.height
    then
      result[#result + 1] =
        { code = "tile_image_grid_mismatch", tileset_index = tsi, tile_index = index }
    end
  end
  return result
end

local function cell_findings(sprite, layer, frame, findings)
  local cel = layer:cel(frame)
  if cel == nil then return end
  for y = 0, cel.image.height - 1 do
    for x = 0, cel.image.width - 1 do
      local packed = cel.image:getPixel(x, y)
      local index = app.pixelColor.tileI(packed)
      local code
      if index >= #layer.tileset then
        code = "tile_index_out_of_bounds"
      elseif index == 0 and packed ~= 0 then
        code = "empty_tile_flags"
      end
      if code then
        findings[#findings + 1] = {
          code = code,
          tileset_index = tileset_index(sprite, layer.tileset),
          tile_index = index,
          layer_path = layers.current_path(sprite, layer),
          frame_number = frame,
          tile_x = x,
          tile_y = y,
        }
      end
    end
  end
end

function module.read(sprite, payload)
  local uuids = sprites.saved_layer_uuids(sprite, payload.sprite_file)
  local result = {
    status = "success",
    operation = "spa " .. payload.operation,
    sprite_file = payload.sprite_file,
    complete = true,
  }
  local operation = payload.operation
  if operation == "tileset list" or operation == "tilemap list" then
    result.tilesets = {}
    for index, tileset in ipairs(sprite.tilesets) do
      result.tilesets[#result.tilesets + 1] = facts(sprite, tileset, index, uuids)
    end
    if operation == "tilemap list" then
      result.frame_count, result.cels = #sprite.frames, {}
      for _, layer in ipairs(tilemap_layers(sprite)) do
        for _, cel in ipairs(layer.cels) do
          result.cels[#result.cels + 1] = cel_facts(sprite, layer, cel.frame.frameNumber, uuids)
        end
      end
    end
    return result
  end
  local tileset, tsi, failure = resolve_tileset(sprite, payload.target, uuids)
  if failure then return failure end
  result.tileset = facts(sprite, tileset, tsi, uuids)
  if operation == "tileset get" then
    result.tiles = {}
    for index = 0, #tileset - 1 do
      result.tiles[#result.tiles + 1] =
        tile_facts(tileset, tileset:tile(index), payload.property_namespaces)
    end
  elseif operation == "tileset tile get" then
    local tile, rejected = resolve_tile(tileset, payload.tile)
    if rejected then return rejected end
    result.tile = tile_facts(tileset, tile, payload.property_namespaces)
    if
      tile.image.width * tile.image.height > payload.inline_pixels
      and not payload.staged_snapshot_file
    then
      return snapshot_limit("pixels", tile.image.width * tile.image.height, payload.inline_pixels)
    end
    return snapshot_output(
      result,
      pixels.read(tile.image, Rectangle(0, 0, tile.image.width, tile.image.height)),
      payload
    )
  elseif operation == "tileset validate" then
    result.findings = key_findings(tileset, tsi)
    for _, layer in ipairs(tilemap_layers(sprite)) do
      if layer.tileset == tileset then
        for _, cel in ipairs(layer.cels) do
          cell_findings(sprite, layer, cel.frame.frameNumber, result.findings)
        end
      end
    end
    result.valid = #result.findings == 0
  else
    local layer, rejected = resolve_layer(sprite, payload.target.layer, uuids)
    if rejected then return rejected end
    local frame = integer(payload.target.frame_number, 1, #sprite.frames)
    if frame == nil then
      return reject("tilemap_frame_out_of_bounds", "Frame is outside the current Sprite timeline")
    end
    result.tilemap = cel_facts(sprite, layer, frame, uuids)
    if operation == "tilemap validate" then
      result.findings = key_findings(tileset, tsi)
      cell_findings(sprite, layer, frame, result.findings)
      result.valid = #result.findings == 0
    else
      result.snapshot, result.output_form = null, "summary"
      if payload.rectangle then
        local cel = layer:cel(frame)
        if not cel then
          return reject("tilemap_cel_missing", "The selected Tilemap Cel is absent")
        end
        local requested = payload.rectangle
        local x, y =
          integer(requested.x, 0, cel.image.width - 1),
          integer(requested.y, 0, cel.image.height - 1)
        local width, height =
          integer(requested.width, 1, cel.image.width),
          integer(requested.height, 1, cel.image.height)
        if
          not x
          or not y
          or not width
          or not height
          or x + width > cel.image.width
          or y + height > cel.image.height
        then
          return reject("tile_region_out_of_bounds", "Tile Cell Rectangle is outside the Cel Image")
        end
        if width * height > payload.inline_cells and not payload.staged_snapshot_file then
          return snapshot_limit("tile_cells", width * height, payload.inline_cells)
        end
        return snapshot_output(
          result,
          region(cel.image, tileset, { x = x, y = y, width = width, height = height }),
          payload
        )
      end
    end
  end
  return result
end

return module
