-- Fast deterministic digests for bounded mutation evidence.
local module = {}
local fnv_offset_basis = -3750763034362895579
local fnv_prime = 1099511628211

function module.fnv1a64(...)
  local hash = fnv_offset_basis
  for argument = 1, select("#", ...) do
    local value = select(argument, ...)
    for offset = 1, #value do
      hash = (hash ~ string.byte(value, offset)) * fnv_prime
    end
  end
  return string.format("%016x", hash)
end

function module.image_content(image, color_mode)
  local header = table.concat({
    color_mode,
    ":",
    image.width,
    "x",
    image.height,
    ":",
    image.bytesPerPixel,
    ":",
    image.rowStride,
    ":",
  })
  return { algorithm = "fnv1a64", value = module.fnv1a64(header, image.bytes) }
end

return module
