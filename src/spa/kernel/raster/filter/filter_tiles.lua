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

function module.admit(application, available)
  if application.tileset_mode ~= "manual" then
    return "Tilemap pixel filtering requires explicit tileset_mode: manual"
  end
  if not available then return "Selected runtime lacks Manual Tilemap Filter capability" end
  if app.site.tilesetMode ~= TilesetMode.MANUAL then
    return "Observed native Tileset Mode differs from requested Manual mode"
  end
end

function module.snapshot(sprite, mode)
  local facts = { maps = {}, bindings = {}, tiles = {}, metadata = uses.tile_metadata(sprite) }
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
  for _, cel in ipairs(sprite.cels) do
    if cel.layer.isTilemap then
      facts.maps[#facts.maps + 1] = {
        layer_path = layers.current_path(sprite, cel.layer),
        frame_number = cel.frameNumber,
        x = cel.position.x,
        y = cel.position.y,
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
        cel_uses = tile.cel_uses,
      }
    end
  end
  return facts
end

function module.changes(before, after, targets)
  persistence.assert_equal(before.maps, after.maps, "Manual Filter Tilemap placements")
  persistence.assert_equal(before.bindings, after.bindings, "Manual Filter Tileset bindings")
  persistence.assert_equal(before.metadata, after.metadata, "Manual Filter Tile metadata")
  assert(#before.tiles == #after.tiles, "Manual Filter changed Tile counts")
  local direct, affected, changes = {}, {}, {}
  for _, cel in ipairs(targets.existing_target_cels) do
    direct[address(cel)] = cel.image_number
  end
  for _, cel in ipairs(targets.affected_cels) do
    affected[address(cel)] = cel.image_number
  end
  for i, old in ipairs(before.tiles) do
    local new = after.tiles[i]
    assert(
      old.tileset_index == new.tileset_index and old.tile_index == new.tile_index,
      "Manual Filter changed Tile addresses"
    )
    persistence.assert_equal(old.cel_uses, new.cel_uses, "Manual Filter Tile references")
    if old.content_digest.value ~= new.content_digest.value then
      local reachable = false
      local references = {}
      for _, cel in ipairs(old.cel_uses) do
        local key = address(cel)
        local relationships = { "shared-tile" }
        if direct[key] then
          reachable = true
          relationships[#relationships + 1] = "direct-target"
        elseif affected[key] then
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

return module
