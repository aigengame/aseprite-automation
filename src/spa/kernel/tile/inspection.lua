-- Native Tile identities, exact bindings, complete regions, and validation.
local module = {}
local tilesets = dofile(app.params.tilesets)
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

local tilemap_layers = tilesets.tilemap_layers
local facts = tilesets.facts
local resolve_layer = tilesets.resolve_layer
local tileset_index = tilesets.tileset_index
local resolve_tileset = tilesets.resolve_tileset

local keys = dofile(app.params.tile_keys)
local tile_key = keys.observe

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
  local index, failure = keys.resolve(tileset, address.tile_key)
  if failure then return nil, failure end
  return tileset:tile(index)
end

local cel_facts = dofile(app.params.tilemaps).cel_facts

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
    local key, code = null, nil
    -- Tile 0 has no SPA identity; its native Properties view can alias Tileset data.
    if index > 0 then
      key, code = tile_key(tile)
      if not code then
        if seen[key] then
          code = "tile_key_duplicate"
        else
          seen[key] = index
        end
      end
    end
    if code then
      result[#result + 1] = {
        code = code,
        tileset_index = tsi,
        tile_index = index,
        tile_key = key,
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
