-- Color and Palette owns Frame-based resolution; callers own validation and errors.
local module = {}

function module.resolve(sprite, frame_number)
  local selected, change_frame = nil, -1
  for index = 1, #sprite.palettes do
    local palette = sprite.palettes[index]
    local candidate = palette.frame.frameNumber
    if candidate <= frame_number and candidate > change_frame then
      selected, change_frame = palette, candidate
    end
  end
  return selected, change_frame
end

return module
