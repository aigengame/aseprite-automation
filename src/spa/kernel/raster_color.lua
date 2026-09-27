-- Shared Raster Color Values and native Effective Palette observations.
local module = {}

local function copy_color(color)
  if color.kind == "rgba" then
    return {
      kind = "rgba",
      red = color.red,
      green = color.green,
      blue = color.blue,
      alpha = color.alpha,
    }
  elseif color.kind == "grayscale" then
    return { kind = "grayscale", gray = color.gray, alpha = color.alpha }
  end
  return { kind = "palette-index", index = color.index }
end

local function colors_equal(left, right)
  if left.kind ~= right.kind then return false end
  if left.kind == "rgba" then
    return left.red == right.red
      and left.green == right.green
      and left.blue == right.blue
      and left.alpha == right.alpha
  elseif left.kind == "grayscale" then
    return left.gray == right.gray and left.alpha == right.alpha
  end
  return left.index == right.index
end

local function color_mode_name(sprite)
  if sprite.colorMode == ColorMode.RGB then return "rgb" end
  if sprite.colorMode == ColorMode.GRAY then return "grayscale" end
  if sprite.colorMode == ColorMode.INDEXED then return "indexed" end
  error("unsupported target Color Mode")
end

local function validate_byte(value, label)
  assert(
    type(value) == "number" and value % 1 == 0 and value >= 0 and value <= 255,
    "invalid " .. label
  )
end

local function native_color(color, color_mode, background)
  assert(color ~= nil, "missing Color Value")
  if color_mode == "rgb" then
    assert(color.kind == "rgba", "RGB target requires rgba Color Values")
    validate_byte(color.red, "red component")
    validate_byte(color.green, "green component")
    validate_byte(color.blue, "blue component")
    validate_byte(color.alpha, "alpha component")
    if background then assert(color.alpha == 255, "Background RGB write must be opaque") end
    return app.pixelColor.rgba(color.red, color.green, color.blue, color.alpha)
  elseif color_mode == "grayscale" then
    assert(color.kind == "grayscale", "Grayscale target requires grayscale Color Values")
    validate_byte(color.gray, "gray component")
    validate_byte(color.alpha, "alpha component")
    if background then assert(color.alpha == 255, "Background Grayscale write must be opaque") end
    return app.pixelColor.graya(color.gray, color.alpha)
  end
  assert(color.kind == "palette-index", "Indexed target requires palette-index Color Values")
  validate_byte(color.index, "Palette Index")
  return color.index
end

local function effective_palette(sprite, frame_number)
  local selected = nil
  local selected_frame = -1
  for palette_index = 1, #sprite.palettes do
    local palette = sprite.palettes[palette_index]
    local palette_frame = palette.frame.frameNumber
    if palette_frame <= frame_number and palette_frame > selected_frame then
      selected = palette
      selected_frame = palette_frame
    end
  end
  assert(selected ~= nil, "Indexed target has no Effective Palette")
  return selected, selected_frame
end

local function palette_facts(sprite, affected_cels, used_indexes)
  if sprite.colorMode ~= ColorMode.INDEXED then return {} end
  local frames = {}
  for _, cel in ipairs(affected_cels) do
    frames[cel.frame_number] = true
  end
  local frame_numbers = {}
  for frame_number, _ in pairs(frames) do
    frame_numbers[#frame_numbers + 1] = frame_number
  end
  table.sort(frame_numbers)
  local indexes = {}
  for index, _ in pairs(used_indexes) do
    indexes[#indexes + 1] = index
  end
  table.sort(indexes)
  local result = {}
  for _, frame_number in ipairs(frame_numbers) do
    local palette, palette_frame = effective_palette(sprite, frame_number)
    local index_facts = {}
    for _, index in ipairs(indexes) do
      assert(
        index < #palette,
        "Palette Index does not exist in every affected Cel Frame Effective Palette"
      )
      local color = palette:getColor(index)
      index_facts[#index_facts + 1] = {
        index = index,
        color = { red = color.red, green = color.green, blue = color.blue, alpha = color.alpha },
      }
    end
    result[#result + 1] = {
      frame_number = frame_number,
      palette_frame_number = palette_frame,
      palette_size = #palette,
      indexes = index_facts,
    }
  end
  return result
end

module.copy_color = copy_color
module.colors_equal = colors_equal
module.color_mode_name = color_mode_name
module.native_color = native_color
module.effective_palette = effective_palette
module.palette_facts = palette_facts
return module
