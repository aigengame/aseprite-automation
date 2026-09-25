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

-- Match Aseprite 1.3.18.5 Palette::findBestfit with the Sprite's transparent
-- index as mask. Native Indexed resize instead derives its mask from RGBA-zero
-- Palette entries, which can be a different index.
local function bestfit(r, g, b, a, entries, palette_size, transparent_index)
  if a < 8 then return transparent_index end
  local qr, qg, qb, qa = r // 8, g // 8, b // 8, a // 8
  local chosen, distance = 0, math.huge
  for index = 0, palette_size - 1 do
    if index ~= transparent_index then
      local color = entries[index]
      local dr, dg, db, da = color.r - qr, color.g - qg, color.b - qb, color.a - qa
      local candidate = dr * dr * 900 + dg * dg * 3481 + db * db * 121 + da * da * 64
      if candidate < distance then
        chosen, distance = index, candidate
        if distance == 0 then break end
      end
    end
  end
  return chosen
end

local function resize_indexed_bilinear(source, palette, transparent_index, width, height)
  local rgb = Image(source.width, source.height, ColorMode.RGB)
  local alpha = Image(source.width, source.height, ColorMode.GRAY)
  local colors, entries = {}, {}
  local palette_size = #palette
  local mapped_size = math.min(palette_size, 256)
  local missing = Color { r = 0, g = 0, b = 0, a = 0 }
  for index = 0, 255 do
    -- Native Palette::getEntry returns RGBA zero for an index beyond its size.
    local color = index < palette_size and palette:getColor(index) or missing
    local opacity = index == transparent_index and 0 or color.alpha
    -- RGB resize repairs fully transparent source pixels. Keep their original RGB
    -- during interpolation; the separate alpha image carries their real opacity.
    colors[index] = {
      rgb = app.pixelColor.rgba(color.red, color.green, color.blue, math.max(opacity, 1)),
      alpha = app.pixelColor.graya(0, opacity),
    }
    if index < mapped_size then
      entries[index] = {
        r = color.red // 8,
        g = color.green // 8,
        b = color.blue // 8,
        a = color.alpha // 8,
      }
    end
  end
  for y = 0, source.height - 1 do
    for x = 0, source.width - 1 do
      local color = colors[source:getPixel(x, y)]
      rgb:putPixel(x, y, color.rgb)
      alpha:putPixel(x, y, color.alpha)
    end
  end
  rgb:resize { width = width, height = height, method = "bilinear" }
  alpha:resize { width = width, height = height, method = "bilinear" }
  local indexed = Image(ImageSpec {
    width = width,
    height = height,
    colorMode = ColorMode.INDEXED,
    transparentColor = transparent_index,
  })
  local mapped = {}
  for y = 0, height - 1 do
    for x = 0, width - 1 do
      local pixel = rgb:getPixel(x, y)
      local r, g, b, a =
        app.pixelColor.rgbaR(pixel),
        app.pixelColor.rgbaG(pixel),
        app.pixelColor.rgbaB(pixel),
        app.pixelColor.grayaA(alpha:getPixel(x, y))
      local key = ((r // 8) * 32 + g // 8) * 32 * 32 + (b // 8) * 32 + a // 8
      local index = mapped[key]
      if index == nil then
        index = bestfit(r, g, b, a, entries, mapped_size, transparent_index)
        mapped[key] = index
      end
      indexed:putPixel(x, y, index)
    end
  end
  return indexed
end

function module.resize(source, sprite, width, height, method, palette_frame_number)
  assert(math.tointeger(width) and width > 0, "width must be a positive integer")
  assert(math.tointeger(height) and height > 0, "height must be a positive integer")
  assert(
    method == "nearest-neighbor" or method == "bilinear" or method == "rotsprite",
    "unsupported Image Resize method"
  )
  local basis, selected_palette = nil, nil
  local indexed_bilinear = source.colorMode == ColorMode.INDEXED and method == "bilinear"
  if indexed_bilinear then
    assert(
      math.tointeger(palette_frame_number)
        and palette_frame_number >= 1
        and palette_frame_number <= #sprite.frames,
      "Indexed bilinear requires an existing Palette Frame Number"
    )
    local change_frame
    selected_palette, change_frame = effective_palette(sprite, palette_frame_number)
    assert(selected_palette ~= nil, "Indexed bilinear requires an Effective Palette")
    basis = {
      requested_frame_number = palette_frame_number,
      palette_frame_number = change_frame,
      palette_size = #selected_palette,
      transparent_color_index = sprite.transparentColor,
    }
  else
    assert(palette_frame_number == nil, "Palette Frame Number is not applicable")
  end
  local resized
  if indexed_bilinear then
    resized =
      resize_indexed_bilinear(source, selected_palette, sprite.transparentColor, width, height)
  else
    -- Native non-nearest resize repairs hidden transparent colors in its source.
    -- The detached copy keeps that preprocessing out of the shared Image.
    resized = Image(source)
    resized:resize { width = width, height = height, method = method }
  end
  assert(resized.width == width and resized.height == height, "native Image Resize changed size")
  return resized, basis
end

return module
