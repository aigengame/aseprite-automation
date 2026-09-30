-- Pure stored-pixel transforms. Cel placement and Palette validity belong to callers.
local module = {}

local function rectangle(x, y, width, height)
  return { x = x, y = y, width = width, height = height }
end

local function remainder(width, height, kept)
  if kept.width == 0 or kept.height == 0 then return { rectangle(0, 0, width, height) } end
  local regions = {}
  local function add(x, y, w, h)
    if w > 0 and h > 0 then regions[#regions + 1] = rectangle(x, y, w, h) end
  end
  add(0, 0, width, kept.y)
  add(0, kept.y, kept.x, kept.height)
  add(kept.x + kept.width, kept.y, width - kept.x - kept.width, kept.height)
  add(0, kept.y + kept.height, width, height - kept.y - kept.height)
  return regions
end

local function copy(source, width, height, offset, pixel)
  local spec = ImageSpec(source.spec)
  spec.width, spec.height = width, height
  local result = Image(spec)
  if pixel ~= nil then result:clear(pixel) end
  local left, top = math.max(0, offset.x), math.max(0, offset.y)
  local right, bottom =
    math.min(width, offset.x + source.width), math.min(height, offset.y + source.height)
  local copied_source, copied_target = rectangle(0, 0, 0, 0), rectangle(0, 0, 0, 0)
  if left < right and top < bottom then
    copied_source = rectangle(left - offset.x, top - offset.y, right - left, bottom - top)
    copied_target = rectangle(left, top, right - left, bottom - top)
    for y = top, bottom - 1 do
      for x = left, right - 1 do
        result:putPixel(x, y, source:getPixel(x - offset.x, y - offset.y))
      end
    end
  end
  return result,
    {
      source_bounds = rectangle(0, 0, source.width, source.height),
      target_bounds = rectangle(0, 0, width, height),
      copied_source_rectangle = copied_source,
      copied_target_rectangle = copied_target,
      discarded_source_regions = remainder(source.width, source.height, copied_source),
      uncovered_target_regions = remainder(width, height, copied_target),
    }
end

function module.contains_rectangle(source, area)
  return area.x >= 0
    and area.y >= 0
    and area.x + area.width <= source.width
    and area.y + area.height <= source.height
end

function module.crop(source, area)
  assert(
    math.tointeger(area.width)
      and area.width > 0
      and math.tointeger(area.height)
      and area.height > 0,
    "Crop requires exact positive dimensions"
  )
  assert(math.tointeger(area.x) and math.tointeger(area.y), "Crop requires integer coordinates")
  assert(
    module.contains_rectangle(source, area),
    "Crop Rectangle must be contained in the source Image"
  )
  return copy(source, area.width, area.height, { x = -area.x, y = -area.y })
end

function module.compatible_fill(source, fill)
  return (source.colorMode == ColorMode.RGB and fill.kind == "rgba")
    or (source.colorMode == ColorMode.GRAY and fill.kind == "grayscale")
    or (source.colorMode == ColorMode.INDEXED and fill.kind == "palette-index")
end

function module.canvas_resize(source, width, height, offset, fill)
  assert(
    math.tointeger(width) and width > 0 and math.tointeger(height) and height > 0,
    "Canvas Resize requires exact positive dimensions"
  )
  assert(
    math.tointeger(offset.x) and math.tointeger(offset.y),
    "Canvas Resize requires integer offsets"
  )
  assert(
    module.compatible_fill(source, fill),
    "Fill Color Value is incompatible with source Color Mode"
  )
  local pixel
  if fill.kind == "rgba" then
    pixel = app.pixelColor.rgba(fill.red, fill.green, fill.blue, fill.alpha)
  elseif fill.kind == "grayscale" then
    pixel = app.pixelColor.graya(fill.gray, fill.alpha)
  else
    -- JSON numbers are Lua floats. Aseprite treats only a Lua integer as a
    -- stored pixel; a float goes through Color conversion and Palette matching.
    pixel = assert(math.tointeger(fill.index), "Fill Palette Index must be an integer")
  end
  return copy(source, width, height, offset, pixel)
end

return module
