-- Canonical complete Raster exchange. Native Image content stays in the Kernel.
local module = {}

function module.mode(image)
  return assert(
    ({
      [ColorMode.RGB] = "rgb",
      [ColorMode.GRAY] = "grayscale",
      [ColorMode.INDEXED] = "indexed",
    })[image.colorMode],
    "unsupported Image Color Mode"
  )
end

function module.color(pixel, mode)
  local pc = app.pixelColor
  if mode == "rgb" then
    return {
      kind = "rgba",
      red = pc.rgbaR(pixel),
      green = pc.rgbaG(pixel),
      blue = pc.rgbaB(pixel),
      alpha = pc.rgbaA(pixel),
    }
  elseif mode == "grayscale" then
    return { kind = "grayscale", gray = pc.grayaV(pixel), alpha = pc.grayaA(pixel) }
  end
  return { kind = "palette-index", index = pixel }
end

function module.rectangle(area)
  return { x = area.x, y = area.y, width = area.width, height = area.height }
end

function module.read(image, area)
  assert(
    area.width > 0
      and area.height > 0
      and area.x >= 0
      and area.y >= 0
      and area.x + area.width <= image.width
      and area.y + area.height <= image.height,
    "Image Pixel Rectangle is outside Image bounds"
  )
  local mode, rows = module.mode(image), {}
  for y = area.y, area.y + area.height - 1 do
    local row, previous = {}, nil
    for x = area.x, area.x + area.width - 1 do
      local pixel = image:getPixel(x, y)
      if pixel == previous then
        row[#row].length = row[#row].length + 1
      else
        row[#row + 1] = { length = 1, color = module.color(pixel, mode) }
      end
      previous = pixel
    end
    rows[#rows + 1] = row
  end
  return {
    coordinate_space = "image-pixel",
    color_mode = mode,
    rectangle = { x = 0, y = 0, width = area.width, height = area.height },
    rows = rows,
  }
end

return module
