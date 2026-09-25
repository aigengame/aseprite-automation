-- Fixed Image-buffer resize semantic shared by Image and future Tile authors.
local module = {}

local function effective_palette(sprite, frame_number)
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

function module.resize(source, sprite, width, height, method, palette_frame_number)
  assert(math.tointeger(width) and width > 0, "width must be a positive integer")
  assert(math.tointeger(height) and height > 0, "height must be a positive integer")
  assert(
    method == "nearest-neighbor" or method == "bilinear" or method == "rotsprite",
    "unsupported Image Resize method"
  )
  local basis = nil
  local indexed_bilinear = source.colorMode == ColorMode.INDEXED and method == "bilinear"
  if indexed_bilinear then
    assert(
      math.tointeger(palette_frame_number)
        and palette_frame_number >= 1
        and palette_frame_number <= #sprite.frames,
      "Indexed bilinear requires an existing Palette Frame Number"
    )
    local palette, change_frame = effective_palette(sprite, palette_frame_number)
    assert(palette ~= nil, "Indexed bilinear requires an Effective Palette")
    basis = {
      requested_frame_number = palette_frame_number,
      palette_frame_number = change_frame,
      palette_size = #palette,
      transparent_color_index = sprite.transparentColor,
    }
  else
    assert(palette_frame_number == nil, "Palette Frame Number is not applicable")
  end
  local previous = indexed_bilinear
      and { sprite = app.activeSprite, layer = app.activeLayer, frame = app.activeFrame }
    or nil
  local ok, resized = pcall(function()
    if indexed_bilinear then
      app.activeSprite = sprite
      app.activeFrame = sprite.frames[palette_frame_number]
    end
    -- Native non-nearest resize repairs hidden transparent colors in its source.
    -- The detached copy keeps that preprocessing out of the source shared Image.
    local copy = Image(source)
    copy:resize { width = width, height = height, method = method }
    assert(copy.width == width and copy.height == height, "native Image Resize changed size")
    return copy
  end)
  if previous ~= nil then
    app.activeSprite = previous.sprite
    if previous.sprite ~= nil then
      app.activeLayer = previous.layer
      app.activeFrame = previous.frame
    end
  end
  if not ok then error(resized, 0) end
  return resized, basis
end

return module
