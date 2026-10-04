-- Tile lifecycle keeps native Tile records and remaps complete original Cel Images.
local module = {}
local tilesets = dofile(app.params.tilesets)
local inspection = dofile(app.params.inspection)
local properties = dofile(app.params.tile_properties)
local pixels = dofile(app.params.image_snapshot)
local colors = dofile(app.params.raster_color)
local persistence = dofile(app.params.persistence)
local digest = dofile(app.params.digest)
local null = json.decode("null")
local sections = { "frames", "tags", "palettes", "layers", "cels", "slices", "tilesets" }

local function reject(payload, reason, message)
  return {
    rejection = {
      code = "tile_lifecycle_invalid",
      message = message,
      details = {
        kind = "tile_lifecycle",
        target = payload.target,
        reason = reason,
        message = message,
      },
    },
  }
end

local function check_limit(payload, unit, requested)
  local maximum = assert(payload.operation_limits[unit], "missing Tile Operation Limit")
  if requested <= maximum then return nil end
  local failure = reject(
    payload,
    "operation_limit",
    string.format("Tile lifecycle %s count %d exceeds maximum %d", unit, requested, maximum)
  )
  failure.rejection.details.limit = { unit = unit, requested = requested, maximum = maximum }
  return failure
end

local function copy(value)
  if type(value) ~= "table" then return value end
  local result = {}
  for key, item in pairs(value) do
    result[key] = copy(item)
  end
  return result
end

local tile_keys = dofile(app.params.tile_keys)
local tile_key = tile_keys.observe
local exact_key = tile_keys.resolve

local function identities(tileset)
  local result = {}
  for index = 0, #tileset - 1 do
    result[#result + 1] = { tile_index = index, tile_key = tile_key(tileset:tile(index)) }
  end
  return result
end

local function record(tile)
  local color, image = tile.color, tile.image
  local raw
  if tile.index > 0 then raw = tile.properties("aigengame.spa").tile_key end
  return {
    image = {
      width = image.width,
      height = image.height,
      color_mode = pixels.mode(image),
      content = digest.fnv1a64(image.bytes),
    },
    data = tile.data,
    color = { red = color.red, green = color.green, blue = color.blue, alpha = color.alpha },
    key = properties.observe(raw),
    -- Preserve invalid binary Keys as bytes in invariant checks, without publishing them.
    key_bytes = type(raw) == "string" and digest.fnv1a64(raw) or null,
  }
end

local function records(tileset)
  local result = {}
  for tile_index = 0, #tileset - 1 do
    result[#result + 1] = record(tileset:tile(tile_index))
  end
  return result
end

local function unique_new_key(tileset, payload)
  local key = payload.tile_key
  if type(key) ~= "string" or #key == 0 or not utf8.len(key) then
    return reject(payload, "key_conflict", "Tile Key must be a nonempty UTF-8 string")
  end
  for index = 1, #tileset - 1 do
    if tileset:tile(index).properties("aigengame.spa").tile_key == key then
      return reject(payload, "key_conflict", "Tile Key must be unique within the Tileset")
    end
  end
end

local function prepare_add(sprite, tileset, payload, context)
  local failed = unique_new_key(tileset, payload)
  if failed then return failed end
  local value = payload.image
  local area = value and value.rectangle
  local size = tileset.grid.tileSize
  if
    area == nil
    or area.x ~= 0
    or area.y ~= 0
    or area.width ~= size.width
    or area.height ~= size.height
  then
    return reject(
      payload,
      "image_incompatible",
      "Tile Image must cover the exact Tileset Grid at (0,0)"
    )
  end
  failed = check_limit(payload, "image_pixels", area.width * area.height)
  if failed then return failed end
  local valid, image, used = pcall(pixels.materialize, value, sprite.spec, false)
  if not valid then return reject(payload, "image_incompatible", tostring(image)) end
  if image.colorMode ~= sprite.colorMode then
    return reject(payload, "image_incompatible", "Tile Image Color Mode must match the Sprite")
  end
  if image.colorMode ~= ColorMode.INDEXED then
    for pixel in image:pixels() do
      local packed = pixel()
      local alpha = image.colorMode == ColorMode.RGB and app.pixelColor.rgbaA(packed)
        or app.pixelColor.grayaA(packed)
      if alpha == 0 and packed ~= 0 then
        return reject(
          payload,
          "image_incompatible",
          "Alpha 0 Tile pixels require zero hidden RGB/Gray channels; native Tilesets normalize them"
        )
      end
    end
  end
  context.image = image
  context.new_index = #tileset
  context.image_content_digest = digest.image_content(image, pixels.mode(image))
  if sprite.colorMode == ColorMode.INDEXED then
    local frame = tonumber(payload.palette_frame_number)
    if frame == nil or frame % 1 ~= 0 or frame < 1 or frame > #sprite.frames then
      return reject(
        payload,
        "palette_frame",
        "Indexed Tile add requires an existing explicit Palette Frame"
      )
    end
    frame = math.tointeger(frame)
    local used_ok, palette = pcall(colors.palette_facts, sprite, { { frame_number = frame } }, used)
    if not used_ok then return reject(payload, "palette_index", tostring(palette)) end
    local effective = dofile(app.params.effective_palette).resolve(sprite, frame)
    if effective == nil or sprite.transparentColor >= #effective then
      return reject(
        payload,
        "palette_index",
        "Sprite Transparent Color Index is absent from the Effective Palette"
      )
    end
    context.effective_palette = palette[1]
    context.transparent_index = sprite.transparentColor
  elseif payload.palette_frame_number ~= nil then
    return reject(payload, "palette_frame", "Palette Frame applies only to Indexed Tile Images")
  end
end

local function prepare_assign(tileset, payload, context)
  local index = tonumber(payload.tile_index)
  if index == nil or index % 1 ~= 0 or index < 1 or index >= #tileset then
    return {
      rejection = {
        code = "tile_index_out_of_bounds",
        message = "Assign Key requires a current nonzero Tile Index",
      },
    }
  end
  index = math.tointeger(index)
  if tileset:tile(index).properties("aigengame.spa").tile_key ~= nil then
    return reject(payload, "already_keyed", "Assign Key requires an unkeyed Tile")
  end
  local failed = unique_new_key(tileset, payload)
  if failed then return failed end
  context.new_index = index
end

local function prepare_remove(tileset, payload, context)
  local removed, failed = exact_key(tileset, payload.tile_key)
  if failed then return failed end
  local replacement = payload.replacement
  local replacement_index
  if replacement ~= nil then
    if replacement.kind == "empty" then
      replacement_index = 0
    elseif replacement.kind == "tile" then
      replacement_index, failed = exact_key(tileset, replacement.tile_key)
      if failed then return reject(payload, "replacement_invalid", failed.rejection.message) end
      if replacement_index == removed then
        return reject(payload, "replacement_invalid", "Replacement must survive removal")
      end
    else
      return reject(
        payload,
        "replacement_invalid",
        "Replacement must be Empty or another keyed Tile"
      )
    end
  end
  context.removed_index = removed
  context.removed_tile = copy(context.before_tiles[removed + 1])
  context.empty_replacement = replacement_index == 0
  context.replacement = replacement
      and {
        kind = replacement.kind,
        tile_key = replacement.kind == "tile" and replacement.tile_key or nil,
      }
    or null
  for old = 1, #tileset - 1 do
    if old == removed then
      context.mapping[old] = replacement_index
          and (replacement_index - (replacement_index > removed and 1 or 0))
        or 0
    else
      context.mapping[old] = old - (old > removed and 1 or 0)
    end
  end
end

local function prepare_reorder(tileset, payload, context)
  local keys, requested = {}, payload.tile_keys
  if requested == nil or #requested ~= #tileset - 1 then
    return reject(
      payload,
      "invalid_permutation",
      "Reorder requires every nonempty Tile Key exactly once"
    )
  end
  for index, key in ipairs(requested) do
    if type(key) ~= "string" or #key == 0 or keys[key] then
      return reject(payload, "invalid_permutation", "Reorder Keys must be nonempty and unique")
    end
    keys[key] = index
  end
  local seen = {}
  for old = 1, #tileset - 1 do
    local key = tile_key(tileset:tile(old))
    if key == null or not keys[key] or seen[key] then
      return reject(
        payload,
        "invalid_permutation",
        "Reorder requires uniquely keyed Tiles and a complete permutation"
      )
    end
    seen[key] = true
    context.mapping[old] = keys[key]
  end
  context.desired_keys = copy(requested)
end

local function remapped(packed, context)
  local old = app.pixelColor.tileI(packed)
  -- Flagged index 0 is an observed Placement, and must retain its complete value.
  if old == 0 then return packed end
  if old == context.removed_index and context.empty_replacement then return 0 end
  return context.mapping[old] | app.pixelColor.tileF(packed)
end

local function prepare_placements(sprite, payload, context, uuids)
  local layers = tilesets.tilemap_layers(sprite)
  local cells = 0
  for _, layer in ipairs(layers) do
    if layer.tileset == context.tileset then
      for _, cel in ipairs(layer.cels) do
        -- Each logical Cel contributes its full area, even when the Image is linked.
        cells = cells + cel.image.width * cel.image.height
      end
    end
  end
  local failed = check_limit(payload, "tile_cells", cells)
  if failed then return failed end
  local images, layers_changed = {}, {}
  context.image_updates, context.image_contents = {}, {}
  for _, layer in ipairs(layers) do
    if layer.tileset == context.tileset then
      for _, cel in ipairs(layer.cels) do
        local image, changed = cel.image, 0
        if image.colorMode ~= ColorMode.TILEMAP then
          return reject(payload, "invalid_placement", "Referencing Cel Image is not a Tilemap")
        end
        for pixel in image:pixels() do
          local packed = pixel()
          local old = app.pixelColor.tileI(packed)
          if old >= #context.tileset then
            return reject(
              payload,
              "invalid_placement",
              "Referencing Cell has an out-of-bounds Tile Index"
            )
          end
          if old == context.removed_index and payload.replacement == nil then
            return reject(
              payload,
              "replacement_required",
              "Removing a used Tile requires an explicit replacement"
            )
          end
          if remapped(packed, context) ~= packed then changed = changed + 1 end
        end
        if changed > 0 then
          local update = images[image.id]
          if update == nil then
            local original = Image(image)
            local final = Image(original)
            for y = 0, original.height - 1 do
              for x = 0, original.width - 1 do
                final:putPixel(x, y, remapped(original:getPixel(x, y), context))
              end
            end
            update = {
              cel = cel,
              original = original,
              final = final,
              content = digest.fnv1a64(final.bytes),
            }
            images[image.id] = update
            context.image_updates[#context.image_updates + 1] = update
          end
          context.image_contents[image.id] = update.content
          local facts = tilesets.layer_facts(sprite, layer, uuids)
          context.affected_cels[#context.affected_cels + 1] = {
            layer = facts,
            frame_number = cel.frameNumber,
            changed_cells = changed,
          }
          if not layers_changed[layer] then
            layers_changed[layer] = true
            context.affected_layers[#context.affected_layers + 1] = facts
          end
        end
      end
    end
  end
end

function module.prepare(sprite, payload, uuids)
  local tileset, index, failed = tilesets.resolve_tileset(sprite, payload.target, uuids)
  if failed then return nil, failed end
  -- Removal must also fit its complete before-state mapping; include Empty Tile 0.
  local required_tiles = #tileset + (payload.operation == "add" and 1 or 0)
  failed = check_limit(payload, "tiles", required_tiles)
  if failed then return nil, failed end
  local context = {
    tileset = tileset,
    tileset_index = index,
    operation = payload.operation,
    before_tileset = tilesets.facts(sprite, tileset, index, uuids),
    before_tiles = identities(tileset),
    effective_palette = null,
    transparent_index = null,
    image_content_digest = null,
    mapping = {},
    affected_layers = {},
    affected_cels = {},
  }
  for old = 0, #tileset - 1 do
    context.mapping[old] = old
  end
  if payload.operation == "add" then
    failed = prepare_add(sprite, tileset, payload, context)
  elseif payload.operation == "assign-key" then
    failed = prepare_assign(tileset, payload, context)
  elseif payload.operation == "remove" then
    failed = prepare_remove(tileset, payload, context)
  elseif payload.operation == "reorder" then
    failed = prepare_reorder(tileset, payload, context)
  else
    return nil, reject(payload, "invalid_permutation", "Unsupported Tile lifecycle operation")
  end
  if failed then return nil, failed end
  if payload.operation == "remove" or payload.operation == "reorder" then
    failed = prepare_placements(sprite, payload, context, uuids)
    if failed then return nil, failed end
  end
  context.before = persistence.snapshot(sprite, inspection, digest, sections, uuids)
  context.before_records = records(tileset)
  context.expected_images = {}
  for cel_index, cel in ipairs(sprite.cels) do
    if context.image_contents and context.image_contents[cel.image.id] then
      context.expected_images[cel_index] = context.image_contents[cel.image.id]
    end
  end
  return context
end

local function reorder(sprite, context)
  local previous_layer = app.activeLayer
  app.activeSprite = sprite
  local active
  for _, layer in ipairs(tilesets.tilemap_layers(sprite)) do
    if layer.tileset == context.tileset then
      active = layer
      break
    end
  end
  local temporary
  if active == nil then
    local size = context.tileset.grid.tileSize
    assert(app.command.NewLayer {
      tilemap = true,
      ask = false,
      top = true,
      gridBounds = Rectangle(0, 0, size.width, size.height),
    })
    temporary = app.activeLayer
    local generated = temporary.tileset
    temporary.tileset = context.tileset
    sprite:deleteTileset(generated)
    active = temporary
  end
  app.activeLayer = active
  for final, key in ipairs(context.desired_keys) do
    local current = assert(exact_key(context.tileset, key))
    if current ~= final then
      assert(current > final, "Reorder disturbed its completed prefix")
      app.range.tiles = { current }
      assert(app.command.MoveTiles { before = final }, "native Tile reorder failed")
    end
  end
  if temporary ~= nil then sprite:deleteLayer(temporary) end
  if previous_layer ~= nil then pcall(function() app.activeLayer = previous_layer end) end
end

function module.apply(sprite, payload, context)
  app.transaction("Tile lifecycle", function()
    if payload.operation == "add" then
      local tile = sprite:newTile(context.tileset)
      assert(tile.index == context.new_index and tile.index > 0, "Tile was not appended")
      tile.image = context.image
      tile.properties("aigengame.spa").tile_key = payload.tile_key
    elseif payload.operation == "assign-key" then
      context.tileset:tile(context.new_index).properties("aigengame.spa").tile_key =
        payload.tile_key
    elseif payload.operation == "remove" then
      sprite:deleteTile(context.tileset, context.removed_index)
    elseif payload.operation == "reorder" then
      reorder(sprite, context)
    end
    for _, update in ipairs(context.image_updates or {}) do
      -- ReplaceImage updates all Linked Cels; snapshots and reports use the original IDs.
      update.cel.image = update.final
    end
  end)
end

function module.verify_live(sprite, payload, context, uuids)
  local expected = copy(context.before)
  expected.sprite.tilesets[context.tileset_index].tile_count = #context.tileset
  for cel_index, content in pairs(context.expected_images) do
    expected.images[cel_index].content = content
  end
  persistence.assert_same(
    expected,
    persistence.snapshot(sprite, inspection, digest, sections, uuids),
    "Tile lifecycle invariant"
  )
  local observed = records(context.tileset)
  local expected_records = copy(context.before_records)
  if payload.operation == "add" then
    local added = observed[context.new_index + 1]
    assert(added.image.content == digest.fnv1a64(context.image.bytes), "Added Tile Image differs")
    assert(
      tile_key(context.tileset:tile(context.new_index)) == payload.tile_key,
      "Added Tile Key differs"
    )
    expected_records[#expected_records + 1] = copy(added)
  elseif payload.operation == "assign-key" then
    expected_records[context.new_index + 1].key = { kind = "string", value = payload.tile_key }
    expected_records[context.new_index + 1].key_bytes = digest.fnv1a64(payload.tile_key)
  elseif payload.operation == "remove" or payload.operation == "reorder" then
    local moved = {}
    for old = 0, #expected_records - 1 do
      if old ~= context.removed_index then
        moved[context.mapping[old] + 1] = expected_records[old + 1]
      end
    end
    expected_records = moved
  end
  persistence.assert_equal(expected_records, observed, "Tile content and identity invariant")
  context.live_records = observed
  context.live_tiles = identities(context.tileset)
end

function module.verify_saved(sprite, context)
  persistence.assert_equal(
    context.live_records,
    records(sprite.tilesets[context.tileset_index]),
    "persisted Tile content and identity"
  )
  persistence.assert_equal(
    context.live_tiles,
    identities(sprite.tilesets[context.tileset_index]),
    "persisted Tile index order"
  )
end

function module.observe(sprite, payload, context, uuids)
  local tileset = sprite.tilesets[context.tileset_index]
  local facts = tilesets.facts(sprite, tileset, context.tileset_index, uuids)
  local bindings = {}
  for _, layer in ipairs(facts.layers) do
    bindings[table.concat(layer.layer_path, "/")] = layer
  end
  local affected_layers, affected_cels = {}, {}
  for _, layer in ipairs(context.affected_layers) do
    affected_layers[#affected_layers + 1] = assert(bindings[table.concat(layer.layer_path, "/")])
  end
  for _, cel in ipairs(context.affected_cels) do
    affected_cels[#affected_cels + 1] = {
      layer = assert(bindings[table.concat(cel.layer.layer_path, "/")]),
      frame_number = cel.frame_number,
      changed_cells = cel.changed_cells,
    }
  end
  local mapping = {}
  for _, before in ipairs(context.before_tiles) do
    mapping[#mapping + 1] = {
      old_index = before.tile_index,
      new_index = context.mapping[before.tile_index],
      tile_key = before.tile_key,
    }
  end
  return {
    before_tileset = context.before_tileset,
    tileset = facts,
    before_tiles = context.before_tiles,
    tiles = identities(tileset),
    index_mapping = mapping,
    tile = context.new_index and { tile_index = context.new_index, tile_key = payload.tile_key }
      or null,
    removed_tile = context.removed_tile or null,
    replacement = context.replacement or null,
    effective_palette = context.effective_palette,
    transparent_index = context.transparent_index,
    image_content_digest = context.image_content_digest,
    affected_layers = affected_layers,
    affected_cels = affected_cels,
    sprite = inspection.inspect(sprite, sections, uuids),
    persisted_reopen_verified = true,
  }
end

return module
