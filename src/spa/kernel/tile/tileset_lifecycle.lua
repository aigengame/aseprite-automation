-- Live Tileset lifecycle semantics; the enclosing handler owns staged persistence.
local module = {}
local tilesets = dofile(app.params.tilesets)
local keys = dofile(app.params.tile_keys)
local inspection = dofile(app.params.inspection)
local persistence = dofile(app.params.persistence)
local digest = dofile(app.params.digest)
local colors = dofile(app.params.raster_color)
local palettes = dofile(app.params.effective_palette)
local null = json.decode("null")
local sections = { "frames", "tags", "palettes", "layers", "cels", "slices", "tilesets" }

local function all_facts(sprite, uuids)
  local result = {}
  for index, tileset in ipairs(sprite.tilesets) do
    result[index] = tilesets.facts(sprite, tileset, index, uuids)
  end
  return result
end

function module.checkpoint(sprite, uuids, document)
  local bindings = {}
  for _, layer in ipairs(tilesets.tilemap_layers(sprite)) do
    bindings[#bindings + 1] = {
      layer = tilesets.layer_facts(sprite, layer, uuids),
      tileset_index = assert(tilesets.tileset_index(sprite, layer.tileset)),
    }
  end
  return {
    document = document or persistence.snapshot(sprite, inspection, digest, sections, uuids),
    bindings = bindings,
  }
end

function module.verify_saved(sprite, checkpoint, uuids, document)
  local observed = module.checkpoint(sprite, uuids, document)
  persistence.assert_same(checkpoint.document, observed.document, "Tileset lifecycle")
  persistence.assert_equal(checkpoint.bindings, observed.bindings, "Tileset Layer bindings")
end

local function reject(input, reason, message, frame_number, tile_index)
  return {
    rejection = {
      code = "tileset_lifecycle_invalid",
      message = message,
      details = {
        kind = "tileset_lifecycle",
        target = input.target,
        layer = input.layer or null,
        reason = reason,
        message = message,
        frame_number = frame_number,
        tile_index = tile_index,
      },
    },
  }
end

local function resolve_target(sprite, input, uuids)
  local selected, index, failure = tilesets.resolve_tileset(sprite, input.target, uuids)
  if failure and input.target.layer then failure.rejection.address_role = "target" end
  return selected, index, failure
end

function module.remove_live(sprite, input, uuids)
  local selected, index, failure = resolve_target(sprite, input, uuids)
  if failure then return failure end
  local before_facts = all_facts(sprite, uuids)
  local removed = before_facts[index]
  if #removed.layers > 0 then
    return {
      rejection = {
        code = "tileset_in_use",
        message = "Resolve every Tilemap Layer reference before removing the Tileset",
        details = {
          kind = "tileset_in_use",
          target = input.target,
          tileset = removed,
          layers = removed.layers,
        },
      },
    }
  end
  local expected = module.checkpoint(sprite, uuids)
  table.remove(expected.document.sprite.tilesets, index)
  expected.document.sprite.metadata.tileset_count = #sprite.tilesets - 1
  for _, binding in ipairs(expected.bindings) do
    if binding.tileset_index > index then binding.tileset_index = binding.tileset_index - 1 end
  end
  app.transaction("Remove Tileset", function()
    sprite:deleteTileset(selected)
    module.verify_saved(sprite, expected, uuids)
  end)
  local mapping = {}
  for old = 1, #before_facts do
    mapping[#mapping + 1] = {
      old_index = old,
      new_index = old == index and null or old - (old > index and 1 or 0),
    }
  end
  return {
    before_tilesets = before_facts,
    tilesets = all_facts(sprite, uuids),
    removed_tileset = removed,
    index_mapping = mapping,
    unchanged_facts_verified = true,
  }
end

local function sorted_indexes(set)
  local result = {}
  for index in pairs(set) do
    result[#result + 1] = index
  end
  table.sort(result)
  return result
end

local function coverage(cel, grid)
  return {
    x = cel.position.x + grid.origin.x,
    y = cel.position.y + grid.origin.y,
    width = cel.image.width * grid.tileSize.width,
    height = cel.image.height * grid.tileSize.height,
  }
end

local function used_source_tiles(layer, source, input)
  local used = {}
  for _, cel in ipairs(layer.cels) do
    if cel.image.colorMode ~= ColorMode.TILEMAP then
      return nil, reject(input, "invalid_placement", "Cel Image is not a Tilemap", cel.frameNumber)
    end
    for pixel in cel.image:pixels() do
      local packed = pixel()
      if packed ~= 0 then
        local index = app.pixelColor.tileI(packed)
        if index >= #source then
          return nil,
            reject(
              input,
              "invalid_placement",
              "Cell refers to a Tile Index outside the source Tileset",
              cel.frameNumber,
              index
            )
        end
        if used[index] == nil then
          local key = keys.observe(source:tile(index))
          if key == null then
            return nil,
              {
                rejection = {
                  code = "tile_key_missing",
                  message = "Every used source Tile Placement requires a Tile Key",
                },
              }
          end
          local _, failure = keys.resolve(source, key)
          if failure then return nil, failure end
          used[index] = key
        end
      end
    end
  end
  return used
end

local function prepare_mapping(target, used, input)
  local explicit = {}
  if input.mapping.kind == "explicit" then
    local required = {}
    for _, key in pairs(used) do
      required[key] = true
    end
    for _, entry in ipairs(input.mapping.entries) do
      if explicit[entry.source_key] or not required[entry.source_key] then
        return nil,
          nil,
          reject(
            input,
            "mapping_invalid",
            "Explicit mapping must contain each used source Tile Key exactly once"
          )
      end
      explicit[entry.source_key] = entry.target
    end
    for key in pairs(required) do
      if explicit[key] == nil then
        return nil,
          nil,
          reject(input, "mapping_incomplete", "A used source Tile Key has no mapping")
      end
    end
  elseif input.mapping.kind ~= "by_key" then
    return nil, nil, reject(input, "mapping_invalid", "Unsupported Tile Key mapping kind")
  end
  local mapping, facts = {}, {}
  for _, index in ipairs(sorted_indexes(used)) do
    local key = used[index]
    local destination = input.mapping.kind == "by_key" and { kind = "tile", tile_key = key }
      or explicit[key]
    local target_index, failure
    if destination.kind == "empty" then
      target_index = 0
    elseif destination.kind == "tile" then
      target_index, failure = keys.resolve(target, destination.tile_key)
      if failure then return nil, nil, failure end
    else
      return nil,
        nil,
        reject(input, "mapping_invalid", "Mapping target must be a Tile Key or Empty")
    end
    mapping[index] = target_index
    facts[#facts + 1] = {
      source_tile_key = key,
      source_index = index,
      target_tile_key = target_index == 0 and null or destination.tile_key,
      target_index = target_index,
    }
  end
  return mapping, facts
end

local function prepare_images(layer, source, target, mapping)
  local updates, cels = {}, {}
  for _, cel in ipairs(layer.cels) do
    local original = cel.image
    local update = updates[original.id]
    if update == nil then
      local final, changed, used, source_indexes = Image(original), 0, {}, {}
      for y = 0, original.height - 1 do
        for x = 0, original.width - 1 do
          local packed = original:getPixel(x, y)
          local output = 0
          if packed ~= 0 then
            local source_index = app.pixelColor.tileI(packed)
            source_indexes[source_index] = true
            local destination = assert(mapping[source_index])
            if destination > 0 then
              output = destination | app.pixelColor.tileF(packed)
              used[destination] = true
            end
          end
          final:putPixel(x, y, output)
          if output ~= packed then changed = changed + 1 end
        end
      end
      update = {
        cel = cel,
        final = final,
        content = digest.fnv1a64(final.bytes),
        changed = changed,
        used = sorted_indexes(used),
        source_indexes = sorted_indexes(source_indexes),
      }
      updates[original.id] = update
    end
    cels[#cels + 1] = {
      frame_number = cel.frameNumber,
      position = { x = cel.position.x, y = cel.position.y },
      cell_size = { width = original.width, height = original.height },
      before_coverage = coverage(cel, source.grid),
      canvas_coverage = coverage(cel, target.grid),
      changed_cells = update.changed,
      used_source_indexes = update.source_indexes,
      used_target_indexes = update.used,
    }
  end
  return updates, cels
end

local function validate_palettes(sprite, source, target, mapping, cels, input)
  if sprite.colorMode ~= ColorMode.INDEXED then return {}, null end
  local checks = {}
  for _, cel in ipairs(cels) do
    local changed = {}
    for _, index in ipairs(cel.used_source_indexes) do
      local destination = mapping[index]
      if destination > 0 and (source ~= target or destination ~= index) then
        changed[destination] = true
      end
    end
    local changed_indexes = sorted_indexes(changed)
    if #changed_indexes > 0 then
      local palette, palette_frame = palettes.resolve(sprite, cel.frame_number)
      local function palette_rejection(message, tile_index, invalid_index)
        local failure = reject(input, "palette_index", message, cel.frame_number, tile_index)
        local details = failure.rejection.details
        details.palette_frame_number = palette and palette_frame or nil
        details.palette_size = palette and #palette or 0
        details.invalid_index = invalid_index
        return nil, nil, failure
      end
      if palette == nil or sprite.transparentColor < 0 or sprite.transparentColor >= #palette then
        return palette_rejection(
          "Sprite Transparent Color Index is absent from the usage Frame Effective Palette",
          nil,
          sprite.transparentColor
        )
      end
      local used = {}
      for _, index in ipairs(changed_indexes) do
        local image = target:tile(index).image
        if image.colorMode ~= ColorMode.INDEXED then
          return palette_rejection("Indexed rebind requires Indexed target Tile Bitmaps", index)
        end
        for pixel in image:pixels() do
          local value = pixel()
          if value < 0 or value >= #palette then
            return palette_rejection(
              "Target Tile pixel index is absent from the usage Frame Effective Palette",
              index,
              value
            )
          end
          used[value] = true
        end
      end
      local effective = colors.palette_facts(sprite, { cel }, used)[1]
      checks[#checks + 1] = {
        frame_number = cel.frame_number,
        tile_indexes = changed_indexes,
        effective_palette = effective,
      }
    end
  end
  return checks, sprite.transparentColor
end

function module.rebind_live(sprite, input, uuids)
  local layer, failure = tilesets.resolve_layer(sprite, input.layer, uuids)
  if failure then return failure end
  local target, target_index
  target, target_index, failure = resolve_target(sprite, input, uuids)
  if failure then return failure end
  local source = layer.tileset
  local source_index = assert(tilesets.tileset_index(sprite, source))
  local changed_grid = not persistence.equal(tilesets.grid(source.grid), tilesets.grid(target.grid))
  if input.grid_policy == "require_equal" then
    if changed_grid then
      return reject(input, "grid_mismatch", "Source and target Tileset Grids must be equal")
    end
  elseif input.grid_policy ~= "use_target" then
    return reject(input, "grid_mismatch", "Rebind requires an explicit Grid policy")
  end
  local used
  used, failure = used_source_tiles(layer, source, input)
  if failure then return failure end
  local mapping, mapping_facts
  mapping, mapping_facts, failure = prepare_mapping(target, used, input)
  if failure then return failure end
  local updates, cels = prepare_images(layer, source, target, mapping)
  local palette_checks, transparent_index
  palette_checks, transparent_index, failure =
    validate_palettes(sprite, source, target, mapping, cels, input)
  if failure then return failure end
  local before_facts = all_facts(sprite, uuids)
  local layer_fact = tilesets.layer_facts(sprite, layer, uuids)
  local expected = module.checkpoint(sprite, uuids)
  for _, binding in ipairs(expected.bindings) do
    if table.concat(binding.layer.layer_path, "/") == table.concat(layer_fact.layer_path, "/") then
      binding.tileset_index = target_index
    end
  end
  for index, cel in ipairs(sprite.cels) do
    if cel.layer == layer then
      expected.document.images[index].content = updates[cel.image.id].content
      expected.document.sprite.cels[index].bounds = coverage(cel, target.grid)
    end
  end
  app.transaction("Rebind Tileset", function()
    if changed_grid then
      for _, update in pairs(updates) do
        -- This old-Grid Image command restores cached bounds after a later
        -- rollback undoes the binding. Native userdata and links stay intact.
        update.cel.image = Image(update.cel.image)
      end
    end
    layer.tileset = target
    for _, update in pairs(updates) do
      -- SetLayerTileset does not refresh cached Cel bounds. ReplaceImage uses
      -- the current Layer Grid and keeps native Linked CelData shared.
      if update.changed > 0 or changed_grid then update.cel.image = update.final end
    end
    module.verify_saved(sprite, expected, uuids)
  end)
  return {
    before_tilesets = before_facts,
    tilesets = all_facts(sprite, uuids),
    layer = layer_fact,
    before_tileset = before_facts[source_index],
    tileset = tilesets.facts(sprite, target, target_index, uuids),
    tile_mapping = mapping_facts,
    cels = cels,
    palette_checks = palette_checks,
    transparent_index = transparent_index,
    unchanged_facts_verified = true,
  }
end

return module
