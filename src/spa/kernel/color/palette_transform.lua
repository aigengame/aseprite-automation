-- Palette organization semantics; persistence and Effective Palette remain shared.
local module = {}
local palettes = dofile(app.params.palette)
local effective = dofile(app.params.effective_palette)
local persistence = dofile(app.params.persistence)
local inspection = dofile(app.params.inspection)
local digest = dofile(app.params.digest)
local images = dofile(app.params.palette_images)
local sections = { "frames", "tags", "palettes", "layers", "cels", "slices", "tilesets" }

local function reject(reason, frame, message, index, group)
  return {
    rejection = {
      code = "palette_transform_rejected",
      message = message,
      details = {
        reason = reason,
        palette_frame_number = frame,
        index = index,
        cel_uses = group and group.cel_uses or {},
        tile_uses = group and group.tile_uses or {},
      },
    },
  }
end

function module.snapshot(sprite, uuids)
  return {
    document = persistence.snapshot(sprite, inspection, digest, sections, uuids),
    images = images.facts(images.resolve(sprite)),
    tiles = images.tile_metadata(sprite),
  }
end

function module.resize(sprite, payload, uuids)
  local frame = tonumber(payload.palette_frame_number)
  local selected, owner = effective.resolve(sprite, frame)
  if frame > #sprite.frames or owner ~= frame then
    return {
      rejection = {
        code = "palette_change_missing",
        message = "Resize requires an exact existing Palette Change",
        details = {
          palette_frame_number = payload.palette_frame_number,
          frame_count = #sprite.frames,
        },
      },
    }
  end
  local size = tonumber(payload.size)
  local entries = {}
  for _, entry in ipairs(payload.entries) do
    local color = entry.color
    entries[tonumber(entry.index)] =
      { red = color.red, green = color.green, blue = color.blue, alpha = color.alpha }
  end
  if #payload.entries ~= math.max(0, size - #selected) then
    return reject("growth_entries", frame, "Supply exactly the new Palette Entries")
  end
  for index = #selected, size - 1 do
    if entries[index] == nil then
      return reject("growth_entries", frame, "Every new Palette Entry needs an explicit color")
    end
  end
  if size < #selected and sprite.colorMode == ColorMode.INDEXED then
    if sprite.transparentColor >= size then
      return reject(
        "transparent_index_removed",
        frame,
        "Shrink would remove the Transparent Color Index; remap first",
        sprite.transparentColor
      )
    end
    local range = palettes.get(sprite, frame).palette.effective_frame_range
    for _, group in ipairs(images.resolve(sprite)) do
      if
        group.image.colorMode == ColorMode.INDEXED
        and images.in_range(group, range.from_frame, range.to_frame, true)
      then
        for pixel in group.image:pixels() do
          if pixel() >= size then
            return reject(
              "index_removed",
              frame,
              "Shrink would remove an index still used by an Image; remap first",
              pixel(),
              group
            )
          end
        end
      end
    end
  end
  local expected = module.snapshot(sprite, uuids)
  for _, palette in ipairs(expected.document.sprite.palettes) do
    if palette.frame_number == frame then
      for index = #selected, size - 1 do
        local color = entries[index]
        palette.entries[#palette.entries + 1] = { index = index, color = color }
      end
      for index = #palette.entries, size + 1, -1 do
        palette.entries[index] = nil
      end
    end
  end
  app.transaction("Resize Palette", function()
    selected:resize(size)
    for index, color in pairs(entries) do
      selected:setColor(
        index,
        Color { r = color.red, g = color.green, b = color.blue, a = color.alpha }
      )
    end
  end)
  persistence.assert_equal(expected, module.snapshot(sprite, uuids), "Palette resize")
  return palettes.list(sprite)
end

local function map_indexes(sprite, payload, uuids, reorder)
  if not reorder and sprite.colorMode ~= ColorMode.INDEXED then
    return reject("color_mode", 1, "Remap Colors requires an Indexed Sprite")
  end
  local scope = reorder and payload.scope or "sprite"
  local frame = scope == "palette-change" and tonumber(payload.palette_frame_number) or nil
  local timeline = palettes.list(sprite)
  local from_frame, to_frame = 1, #sprite.frames
  if frame ~= nil then
    local _, owner = effective.resolve(sprite, frame)
    if frame > #sprite.frames or frame ~= owner then
      return {
        rejection = {
          code = "palette_change_missing",
          message = "Reorder requires an exact existing Palette Change",
          details = {
            palette_frame_number = payload.palette_frame_number,
            frame_count = #sprite.frames,
          },
        },
      }
    end
    local range = palettes.get(sprite, frame).palette.effective_frame_range
    from_frame, to_frame = range.from_frame, range.to_frame
  end
  local selected_changes = {}
  for _, change in ipairs(timeline.palette_changes) do
    if frame == nil or change.palette_frame_number == frame then
      if reorder and #payload.mapping ~= #change.entries then
        return reject(
          "permutation_size",
          change.palette_frame_number,
          "Complete permutation must match every selected Palette size"
        )
      end
      selected_changes[#selected_changes + 1] = change
    end
  end
  local mapping, reported = {}, {}
  for _, pair in ipairs(payload.mapping) do
    local old, new = tonumber(pair.old_index), tonumber(pair.new_index)
    if not reorder and (old > 255 or new > 255) then
      return reject(
        "invalid_destination",
        1,
        "Indexed pixels store Palette Indexes from 0 through 255"
      )
    end
    for _, change in ipairs(selected_changes) do
      if new >= #change.entries then
        return reject(
          "invalid_destination",
          change.palette_frame_number,
          "Mapping destination is absent from an Effective Palette",
          pair.new_index
        )
      end
    end
    mapping[old] = new
    reported[#reported + 1] = { old_index = old, new_index = new }
  end
  local old_mask = sprite.transparentColor
  local new_mask = sprite.colorMode == ColorMode.INDEXED and (mapping[old_mask] or old_mask)
    or old_mask
  if frame ~= nil and new_mask ~= old_mask then
    return reject(
      "transparent_index_moved",
      frame,
      "Palette-change reorder must keep the Transparent Color Index fixed",
      old_mask
    )
  end
  if sprite.colorMode == ColorMode.INDEXED then
    for _, change in ipairs(timeline.palette_changes) do
      if new_mask >= #change.entries or new_mask > 255 then
        return reject(
          "invalid_destination",
          change.palette_frame_number,
          "Resulting Transparent Color Index is absent from a Palette Change",
          new_mask
        )
      end
    end
  end
  local groups = images.resolve(sprite)
  local expected = module.snapshot(sprite, uuids)
  local replacement, result_images = {}, {}
  for index, group in ipairs(groups) do
    local image = group.image
    local inside, outside = images.in_range(group, from_frame, to_frame, frame == nil)
    if image.colorMode == ColorMode.INDEXED and inside then
      local mapped = Image(image)
      -- Every Image is transformed once from its original values, including cyclic mappings.
      for pixel in mapped:pixels() do
        local value = mapping[pixel()] or pixel()
        for _, change in ipairs(selected_changes) do
          local range = change.effective_frame_range
          if
            images.in_range(group, range.from_frame, range.to_frame, frame == nil)
            and (value >= #change.entries or value > 255)
          then
            return reject(
              "invalid_pixel",
              change.palette_frame_number,
              "Resulting Image index is absent from its Effective Palette",
              value,
              group
            )
          end
        end
        pixel(value)
      end
      if outside and mapped.bytes ~= image.bytes then
        return reject(
          "shared_image_outside_range",
          frame,
          "Reorder would change an Image used outside the declared Palette range",
          nil,
          group
        )
      end
      replacement[image.id] = mapped
      expected.images[index].content = digest.fnv1a64(mapped.bytes)
      result_images[#result_images + 1] = {
        cel_uses = group.cel_uses,
        tile_uses = group.tile_uses,
        before_digest = digest.fnv1a64(image.bytes),
        after_digest = digest.fnv1a64(mapped.bytes),
      }
    end
    if new_mask ~= old_mask then expected.images[index].mask = new_mask end
  end
  for index, cel in ipairs(sprite.cels) do
    local mapped = replacement[cel.image.id]
    if mapped ~= nil then expected.document.images[index].content = digest.fnv1a64(mapped.bytes) end
  end
  if reorder then
    for _, change in ipairs(expected.document.sprite.palettes) do
      if frame == nil or change.frame_number == frame then
        local entries = {}
        for _, entry in ipairs(change.entries) do
          local destination = mapping[entry.index]
          entries[destination + 1] = { index = destination, color = entry.color }
        end
        change.entries = entries
      end
    end
  end
  expected.document.sprite.metadata.transparent_color_index = new_mask
  app.transaction(reorder and "Reorder Palette" or "Remap Colors", function()
    for _, group in ipairs(groups) do
      local mapped = replacement[group.image.id]
      -- The native owner setter replaces all shared uses and invalidates Tileset
      -- compression caches. Image.bytes alone would leave saved Tile pixels stale.
      if mapped ~= nil and mapped.bytes ~= group.image.bytes then group.owner.image = mapped end
    end
    if new_mask ~= old_mask then sprite.transparentColor = new_mask end
    if reorder then
      for _, change in ipairs(selected_changes) do
        local palette = effective.resolve(sprite, change.palette_frame_number)
        for _, entry in ipairs(change.entries) do
          local color = entry.color
          palette:setColor(
            mapping[entry.index],
            Color { r = color.red, g = color.green, b = color.blue, a = color.alpha }
          )
        end
      end
    end
  end)
  persistence.assert_equal(expected, module.snapshot(sprite, uuids), "Palette mapping")
  local result = palettes.list(sprite)
  result.scope, result.mapping, result.palette_frame_number = scope, reported, frame
  result.transparent_color_index_before, result.transparent_color_index_after = old_mask, new_mask
  result.affected_images = result_images
  return result
end

function module.remap(sprite, payload, uuids) return map_indexes(sprite, payload, uuids, false) end
function module.reorder(sprite, payload, uuids) return map_indexes(sprite, payload, uuids, true) end

return module
