-- Shared native document facts for staged save/reopen verification.
local module = {}

local function difference(left, right, at)
  if at:match("%.layer_uuid$") and type(left) ~= "string" and type(right) == "string" then
    -- Aseprite may assign a UUID to a Layer when the Sprite is saved.
    return nil
  end
  if type(left) ~= type(right) then
    if tonumber(left) ~= nil and tonumber(left) == tonumber(right) then return nil end
    return at .. " (" .. type(left) .. " / " .. type(right) .. ")"
  end
  if type(left) ~= "table" then
    if left == right then return nil end
    return at
      .. " ("
      .. type(left)
      .. ":"
      .. tostring(left)
      .. " / "
      .. type(right)
      .. ":"
      .. tostring(right)
      .. ")"
  end
  for key, value in pairs(left) do
    local found = difference(value, right[key], at .. "." .. tostring(key))
    if found ~= nil then return found end
  end
  for key, _ in pairs(right) do
    if left[key] == nil then return at .. "." .. tostring(key) end
  end
  return nil
end

function module.snapshot(sprite, inspection, digest, sections, verified_uuids)
  local images, links = {}, {}
  local cels = sprite.cels
  for index, cel in ipairs(cels) do
    local image = cel.image
    images[index] = {
      width = image.width,
      height = image.height,
      bytes_per_pixel = image.bytesPerPixel,
      row_stride = image.rowStride,
      content = digest.fnv1a64(image.bytes),
    }
    for prior = 1, index - 1 do
      if image == cels[prior].image then links[#links + 1] = { prior, index } end
    end
  end
  return {
    sprite = inspection.inspect(sprite, sections, verified_uuids),
    images = images,
    links = links,
  }
end

function module.assert_same(before, after, operation)
  local persisted_palettes = after.sprite.palettes
  if before.sprite.metadata.color_mode ~= "indexed" then
    -- RGB/Grayscale palette entries are not image semantics; native serialization
    -- can normalize their alpha without changing the Sprite's image content.
    before.sprite.palettes = nil
    after.sprite.palettes = nil
  end
  local mismatch = difference(before, after, "document")
  after.sprite.palettes = persisted_palettes
  assert(mismatch == nil, "persisted " .. operation .. " differs at " .. tostring(mismatch))
end

return module
