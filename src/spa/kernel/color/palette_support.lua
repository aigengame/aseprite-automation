-- Palette-owned addressing and observation. Effective resolution has one owner.
local module = {}
local effective = dofile(app.params.effective_palette)
local inspection = dofile(app.params.inspection)

function module.list(sprite)
  local palettes = inspection.inspect(sprite, { "palettes" }).palettes
  table.sort(palettes, function(a, b) return a.frame_number < b.frame_number end)
  local changes = {}
  for index, palette in ipairs(palettes) do
    local next_change = palettes[index + 1]
    changes[#changes + 1] = {
      palette_frame_number = palette.frame_number,
      effective_frame_range = {
        from_frame = palette.frame_number,
        to_frame = next_change and next_change.frame_number - 1 or #sprite.frames,
      },
      entries = palette.entries,
    }
  end
  return { frame_count = #sprite.frames, palette_changes = changes }
end

function module.get(sprite, frame_number)
  if frame_number > #sprite.frames then
    return {
      rejection = {
        code = "palette_frame_out_of_bounds",
        message = "Requested Frame is outside the Sprite timeline",
        details = { frame_number = frame_number, frame_count = #sprite.frames },
      },
    }
  end
  local selected, change_frame = effective.resolve(sprite, frame_number)
  assert(selected ~= nil, "Sprite has no Effective Palette")
  for _, change in ipairs(module.list(sprite).palette_changes) do
    if change.palette_frame_number == change_frame then
      return { frame_number = frame_number, palette = change }
    end
  end
  error("Effective Palette is absent from Palette Changes")
end

function module.set(sprite, payload, verified_uuids)
  local selected, change_frame = effective.resolve(sprite, payload.palette_frame_number)
  if
    payload.palette_frame_number > #sprite.frames or change_frame ~= payload.palette_frame_number
  then
    return {
      rejection = {
        code = "palette_change_missing",
        message = "Entry edits require an exact existing Palette Change",
        details = {
          palette_frame_number = payload.palette_frame_number,
          frame_count = #sprite.frames,
        },
      },
    }
  end
  for _, edit in ipairs(payload.entries) do
    if edit.index >= #selected then
      return {
        rejection = {
          code = "palette_index_out_of_bounds",
          message = "Entry edit is outside the existing Palette",
          details = {
            palette_frame_number = change_frame,
            index = edit.index,
            palette_size = #selected,
          },
        },
      }
    end
  end
  local persistence = dofile(app.params.persistence)
  local digest = dofile(app.params.digest)
  local sections = { "frames", "tags", "palettes", "layers", "cels", "slices", "tilesets" }
  local expected = persistence.snapshot(sprite, inspection, digest, sections, verified_uuids)
  for _, palette in ipairs(expected.sprite.palettes) do
    if palette.frame_number == change_frame then
      for _, edit in ipairs(payload.entries) do
        local color = edit.color
        palette.entries[edit.index + 1].color = {
          red = color.red,
          green = color.green,
          blue = color.blue,
          alpha = color.alpha,
        }
      end
    end
  end
  app.transaction("Set Palette Entries", function()
    for _, edit in ipairs(payload.entries) do
      local color = edit.color
      selected:setColor(
        edit.index,
        Color { r = color.red, g = color.green, b = color.blue, a = color.alpha }
      )
    end
  end)
  local live = persistence.snapshot(sprite, inspection, digest, sections, verified_uuids)
  -- Palette is the edited object even in RGB/Grayscale; no Palette normalization is allowed.
  persistence.assert_equal(expected, live, "Palette Entry edit")
  return module.list(sprite)
end

return module
