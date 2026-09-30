-- Fixed whole-Image orientation semantics; no editor Selection participates.
local module = {}

function module.flip(image, axis)
  assert(axis == "horizontal" or axis == "vertical", "unsupported flip axis")
  image:flip(axis == "horizontal" and FlipType.HORIZONTAL or FlipType.VERTICAL)
end

function module.rotated_point(x, y, width, height, angle)
  if angle == 90 then return height - 1 - y, x end
  if angle == -90 then return y, width - 1 - x end
  assert(angle == 180, "unsupported rotation angle")
  return width - 1 - x, height - 1 - y
end

function module.rotate(source, angle)
  assert(angle == 90 or angle == -90 or angle == 180, "unsupported rotation angle")
  local spec = ImageSpec(source.spec)
  if angle ~= 180 then
    spec.width, spec.height = source.height, source.width
  end
  local rotated = Image(spec)
  for pixel in source:pixels() do
    local x, y = module.rotated_point(pixel.x, pixel.y, source.width, source.height, angle)
    rotated:putPixel(x, y, pixel())
  end
  return rotated
end

return module
