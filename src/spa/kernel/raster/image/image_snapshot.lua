-- Canonical complete Raster exchange. Native Image content stays in the Kernel.
local module = {}
local colors = dofile(app.params.raster_color)

function module.materialize(value, spec, background)
  local area = assert(value.rectangle)
  assert(value.coordinate_space == "image-pixel", "Snapshot must use Image Pixels")
  assert(area.x == 0 and area.y == 0, "Snapshot origin must be (0,0)")
  assert(area.width > 0 and area.height > 0, "Snapshot must have positive dimensions")
  assert(area.width % 1 == 0 and area.height % 1 == 0, "Snapshot dimensions must be integers")
  spec.width, spec.height = area.width, area.height
  local image = Image(spec)
  assert(image.width == area.width and image.height == area.height, "Snapshot dimensions narrowed")
  assert(value.color_mode == module.mode(image), "Snapshot Color Mode differs")
  assert(value.rows ~= nil and #value.rows == image.height, "incomplete Snapshot rows")
  local used = {}
  for y, row in ipairs(value.rows) do
    local x, previous = 0, nil
    for _, run in ipairs(row) do
      assert(
        type(run.length) == "number" and run.length % 1 == 0 and run.length > 0,
        "Snapshot run length must be positive"
      )
      assert(x + run.length <= image.width, "Snapshot row exceeds Image width")
      local pixel = colors.native_color(run.color, value.color_mode, background)
      assert(previous == nil or previous ~= pixel, "adjacent equal Snapshot runs must be merged")
      if value.color_mode == "indexed" then used[pixel] = true end
      for at = x, x + run.length - 1 do
        image:putPixel(at, y - 1, pixel)
      end
      x, previous = x + run.length, pixel
    end
    assert(x == image.width, "incomplete Snapshot row")
  end
  return image, used
end

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
