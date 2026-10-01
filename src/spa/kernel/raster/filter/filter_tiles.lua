-- Manual Tilemap admission, native write invariants, and shared-Tile observations.
-- This module never runs a per-Tile Filter or changes Tileset topology.
local module = {}
local uses = dofile(app.params.palette_images)
local layers = dofile(app.params.layer_select)
local digest = dofile(app.params.digest)
local persistence = dofile(app.params.persistence)
local json_null = json.decode("null")

local function address(cel) return table.concat(cel.layer_path, "/") .. ":" .. cel.frame_number end

function module.anchor(targets)
  for _, item in ipairs(targets.images) do
    if item.cel.layer.isTilemap then return item.cel end
  end
end

function module.admit(application, available, observed_mode)
  if application.tileset_mode ~= "manual" then
    return "Tilemap pixel filtering requires explicit tileset_mode: manual"
  end
  if not available then return "Selected runtime lacks Manual Tilemap Filter capability" end
  if observed_mode ~= TilesetMode.MANUAL then
    return "Observed native Tileset Mode "
      .. tostring(observed_mode)
      .. " differs from requested Manual mode"
  end
end

function module.snapshot(sprite, mode)
  local facts =
    { maps = {}, bindings = {}, tiles = {}, grids = {}, metadata = uses.tile_metadata(sprite) }
  for i = 1, #sprite.tilesets do
    local tileset = sprite.tilesets[i]
    local grid = tileset.grid
    facts.grids[i] = {
      name = tileset.name,
      base_index = tileset.baseIndex,
      tile_count = #tileset,
      x = grid.origin.x,
      y = grid.origin.y,
      width = grid.tileSize.width,
      height = grid.tileSize.height,
    }
  end
  local function visit(siblings)
    for _, layer in ipairs(siblings) do
      if layer.isTilemap then
        local owner
        for i = 1, #sprite.tilesets do
          if layer.tileset == sprite.tilesets[i] then owner = i end
        end
        facts.bindings[#facts.bindings + 1] = {
          layer_path = layers.current_path(sprite, layer),
          tileset_index = assert(owner, "Missing Tilemap Tileset"),
        }
      end
      if layer.isGroup then visit(layer.layers) end
    end
  end
  visit(sprite.layers)
  local image_numbers, image_count = {}, 0
  for _, cel in ipairs(sprite.cels) do
    if cel.layer.isTilemap then
      if not image_numbers[cel.image.id] then
        image_count = image_count + 1
        image_numbers[cel.image.id] = image_count
      end
      facts.maps[#facts.maps + 1] = {
        layer_path = layers.current_path(sprite, cel.layer),
        frame_number = cel.frameNumber,
        x = cel.position.x,
        y = cel.position.y,
        image_number = image_numbers[cel.image.id],
        digest = digest.image_content(cel.image, "tilemap"),
      }
    end
  end
  for _, group in ipairs(uses.resolve(sprite)) do
    for _, tile in ipairs(group.tile_uses) do
      local native = sprite.tilesets[tile.tileset_index]:tile(tile.tile_index)
      facts.tiles[#facts.tiles + 1] = {
        tileset_index = tile.tileset_index,
        tile_index = tile.tile_index,
        tile_key = native.properties("aigengame.spa").tile_key or json_null,
        content_digest = digest.image_content(native.image, mode),
        geometry = {
          width = native.image.width,
          height = native.image.height,
          bytes_per_pixel = native.image.bytesPerPixel,
          mask = native.image.spec.transparentColor,
        },
        cel_uses = tile.cel_uses,
      }
    end
  end
  return facts
end

function module.changes(before, after, targets)
  persistence.assert_equal(before.maps, after.maps, "Manual Filter Tilemap placements")
  persistence.assert_equal(before.bindings, after.bindings, "Manual Filter Tileset bindings")
  persistence.assert_equal(before.grids, after.grids, "Manual Filter Tileset grids and counts")
  persistence.assert_equal(before.metadata, after.metadata, "Manual Filter Tile metadata")
  assert(#before.tiles == #after.tiles, "Manual Filter changed Tile counts")
  local direct, affected, shared, changes = {}, {}, {}, {}
  for _, cel in ipairs(targets.existing_target_cels) do
    direct[address(cel)] = cel.image_number
  end
  for _, cel in ipairs(targets.affected_cels) do
    affected[address(cel)] = cel.image_number
    shared[cel.image_number] = (shared[cel.image_number] or 0) + 1
  end
  for i, old in ipairs(before.tiles) do
    local new = after.tiles[i]
    assert(
      old.tileset_index == new.tileset_index and old.tile_index == new.tile_index,
      "Manual Filter changed Tile addresses"
    )
    persistence.assert_equal(old.cel_uses, new.cel_uses, "Manual Filter Tile references")
    persistence.assert_equal(old.geometry, new.geometry, "Manual Filter Tile geometry")
    if old.content_digest.value ~= new.content_digest.value then
      local reachable = false
      local references = {}
      for _, cel in ipairs(old.cel_uses) do
        local key = address(cel)
        local relationships = { "shared-tile" }
        if direct[key] then
          reachable = true
          relationships[#relationships + 1] = "direct-target"
        end
        if affected[key] and shared[affected[key]] > 1 then
          relationships[#relationships + 1] = "shared-cel-image"
        end
        references[#references + 1] = {
          layer_path = cel.layer_path,
          frame_number = cel.frame_number,
          image_number = affected[key] or json_null,
          relationships = relationships,
        }
      end
      assert(old.tile_index ~= 0 and reachable, "Manual Filter changed Empty or unrelated Tile")
      changes[#changes + 1] = {
        tileset_index = old.tileset_index,
        tile_index = old.tile_index,
        tile_key = old.tile_key,
        before_content_digest = old.content_digest,
        after_content_digest = new.content_digest,
        referencing_cels = references,
      }
    end
  end
  return changes
end

-- Lua cannot enumerate plugin namespaces or retain every native Property type.
-- Compare canonical native User Data bytes instead. Keep structural positions
-- so moving equal metadata between owners cannot pass. Palette chunks may vary
-- with RGB Palette-color filtering and do not own the metadata checked here.
local function read_metadata(file)
  local size = assert(file:seek("end"))
  file:seek("set", 0)
  local header = assert(file:read(128))
  assert(
    #header == 128 and string.unpack("<I2", header, 5) == 0xa5e0,
    "Invalid native metadata snapshot"
  )
  assert(string.unpack("<I4", header) == size, "Incomplete native metadata snapshot")
  local frames = string.unpack("<I2", header, 7)
  local records = {}
  for frame = 1, frames do
    local start = assert(file:seek())
    local frame_header = assert(file:read(16))
    local length, magic = string.unpack("<I4I2", frame_header)
    local finish = start + length
    assert(magic == 0xf1fa and length >= 16 and finish <= size, "Invalid native frame")
    local position = 0
    while file:seek() < finish do
      local at = file:seek()
      local chunk_size, kind = string.unpack("<I4I2", assert(file:read(6)))
      assert(chunk_size >= 6 and at + chunk_size <= finish, "Invalid native metadata chunk")
      if kind ~= 0x0004 and kind ~= 0x0011 and kind ~= 0x2019 then position = position + 1 end
      if kind == 0x2008 or kind == 0x2020 then
        records[#records + 1] = {
          frame = frame,
          position = position,
          kind = kind,
          bytes = assert(file:read(chunk_size - 6)),
        }
      else
        assert(file:seek("set", at + chunk_size))
      end
    end
  end
  assert(file:seek() == size, "Incomplete native metadata frames")
  return records
end

function module.serialized_metadata(sprite)
  local path = assert(app.params.workspace, "Missing Filter workspace")
    .. "/filter-metadata.aseprite"
  os.remove(path)
  local file
  local ok, result = pcall(function()
    assert(sprite:saveCopyAs(path), "Could not serialize Filter User Data")
    file = assert(io.open(path, "rb"), "Missing Filter User Data snapshot")
    return read_metadata(file)
  end)
  if file then file:close() end
  os.remove(path)
  if not ok then error(result, 0) end
  return result
end

return module
