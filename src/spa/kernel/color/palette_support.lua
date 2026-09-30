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

return module
