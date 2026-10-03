-- Tilemap Layer/Tileset creation owns only its explicit native lifecycle seam.
local module = {}
local tilesets = dofile(app.params.tilesets)
local persistence = dofile(app.params.persistence)
local inspection = dofile(app.params.inspection)
local digest = dofile(app.params.digest)
local null = json.decode("null")
local sections = { "frames", "tags", "palettes", "layers", "cels", "slices", "tilesets" }

local function images(sprite)
  local result = {}
  for index, tileset in ipairs(sprite.tilesets) do
    local bitmaps = {}
    for tile_index = 0, #tileset - 1 do
      local image = tileset:tile(tile_index).image
      bitmaps[#bitmaps + 1] = {
        width = image.width,
        height = image.height,
        mode = image.colorMode,
        content = digest.fnv1a64(image.bytes),
      }
    end
    result[index] = bitmaps
  end
  return result
end

function module.prepare(sprite, intent, uuids)
  local context = {
    before_tileset_count = #sprite.tilesets,
    temporary_tilesets_removed = 0,
    shared_tileset_before = null,
    intent = intent.create and "create" or "share",
  }
  if intent.share then
    local selected, index, failure = tilesets.resolve_tileset(sprite, intent.share, uuids)
    if failure then return nil, failure end
    context.shared = selected
    context.shared_tileset_before = tilesets.facts(sprite, selected, index, uuids)
  end
  context.before = persistence.snapshot(sprite, inspection, digest, sections, uuids)
  context.before_images = images(sprite)
  return context
end

function module.create(sprite, intent, context)
  local grid = intent.create and intent.create.grid or context.shared_tileset_before.grid
  local size = grid.tile_size
  app.activeSprite = sprite
  assert(
    app.command.NewLayer {
      tilemap = true,
      ask = false,
      top = true,
      gridBounds = Rectangle(0, 0, size.width, size.height),
    },
    "native Tilemap Layer creation failed"
  )
  local layer = app.activeLayer
  assert(layer.isTilemap and #sprite.tilesets == context.before_tileset_count + 1)
  local created = layer.tileset
  assert(tilesets.tileset_index(sprite, created) == #sprite.tilesets)
  if intent.create then
    created.name = intent.create.name
    created.baseIndex = intent.create.base_index
  else
    layer.tileset = context.shared
    for _, candidate in ipairs(tilesets.tilemap_layers(sprite)) do
      assert(candidate.tileset ~= created, "operation-created Tileset is still referenced")
    end
    -- Delete the exact object made by this invocation, never scan for other orphans.
    sprite:deleteTileset(created)
    context.temporary_tilesets_removed = 1
    assert(layer.tileset == context.shared and #sprite.tilesets == context.before_tileset_count)
  end
  assert(#layer.cels == 0, "native Tilemap Layer unexpectedly has Cels")
  return layer
end

function module.observe(sprite, layer, context, uuids)
  local index = assert(tilesets.tileset_index(sprite, layer.tileset))
  return {
    intent = context.intent,
    tileset = tilesets.facts(sprite, layer.tileset, index, uuids),
    before_tileset_count = context.before_tileset_count,
    tileset_count = #sprite.tilesets,
    initial_cel_count = #layer.cels,
    temporary_tilesets_removed = context.temporary_tilesets_removed,
    shared_tileset_before = context.shared_tileset_before,
  }
end

function module.verify_existing(sprite, context, added_path, uuids)
  local after = persistence.snapshot(sprite, inspection, digest, sections, uuids)
  local siblings = after.sprite.layers
  for index = 1, #added_path - 1 do
    siblings = siblings[added_path[index]].children
  end
  assert(added_path[#added_path] == #siblings, "new Layer was not appended")
  table.remove(siblings)
  after.sprite.metadata.layer_count = after.sprite.metadata.layer_count - 1
  if context.intent == "create" then
    table.remove(after.sprite.tilesets)
    after.sprite.metadata.tileset_count = after.sprite.metadata.tileset_count - 1
  end
  persistence.assert_equal(context.before, after, "existing document after Tilemap Layer creation")
  context.live_images = images(sprite)
  local retained = {}
  for index = 1, #context.before_images do
    retained[index] = context.live_images[index]
  end
  persistence.assert_equal(context.before_images, retained, "existing Tile Images")
end

function module.verify_saved(sprite, context)
  persistence.assert_equal(context.live_images, images(sprite), "persisted Tile Images")
end

return module
