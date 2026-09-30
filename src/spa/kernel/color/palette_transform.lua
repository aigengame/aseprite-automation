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

return module
