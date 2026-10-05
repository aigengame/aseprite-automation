-- Raster-owned binary alpha normalization and literal nontransparent bounds.
local module = {}

function module.opaque_bounds(image)
  assert(image.colorMode == ColorMode.RGB, "Opaque bounds require an RGB Image")
  local left, top, right, bottom = image.width, image.height, -1, -1
  for y = 0, image.height - 1 do
    for x = 0, image.width - 1 do
      if app.pixelColor.rgbaA(image:getPixel(x, y)) > 0 then
        left, top = math.min(left, x), math.min(top, y)
        right, bottom = math.max(right, x), math.max(bottom, y)
      end
    end
  end
  if right < left then return nil end
  return { x = left, y = top, width = right - left + 1, height = bottom - top + 1 }
end

function module.normalize(image, threshold)
  assert(image.colorMode == ColorMode.RGB, "Alpha normalization requires an RGB Image")
  assert(
    math.tointeger(threshold) and threshold >= 1 and threshold <= 255,
    "Alpha threshold must be an integer from 1 through 255"
  )
  local result = Image(image)
  local pc = app.pixelColor
  for pixel in result:pixels() do
    local value = pixel()
    pixel(
      pc.rgbaA(value) < threshold and 0
        or pc.rgba(pc.rgbaR(value), pc.rgbaG(value), pc.rgbaB(value), 255)
    )
  end
  return result, module.opaque_bounds(result)
end

return module
