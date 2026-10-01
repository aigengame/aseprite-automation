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

function module.equal(before, after) return difference(before, after, "document") == nil end

function module.assert_equal(before, after, operation)
  local mismatch = difference(before, after, "document")
  assert(mismatch == nil, operation .. " differs at " .. tostring(mismatch))
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

-- Consumes the original Sprite. On success the caller owns the returned reopened
-- Sprite; on failure this function closes whichever Sprite it still owns.
-- Whole-invocation editor restoration and operation postconditions stay with callers.
function module.save_verified(sprite, staged_path, live_uuids, operation)
  local ok, uuids, facts = pcall(function()
    local inspection = dofile(app.params.inspection)
    local digest = dofile(app.params.digest)
    local sections = { "frames", "tags", "palettes", "layers", "cels", "slices", "tilesets" }
    local live = module.snapshot(sprite, inspection, digest, sections, live_uuids)
    assert(sprite:saveAs(staged_path), "could not save staged Sprite")
    sprite:close()
    sprite = nil
    sprite = assert(app.open(staged_path), "could not reopen staged Sprite")
    local persisted_uuids = inspection.saved_layer_uuids(sprite, staged_path)
    local persisted = module.snapshot(sprite, inspection, digest, sections, persisted_uuids)
    module.assert_same(live, persisted, operation)
    return persisted_uuids, persisted.sprite
  end)
  if not ok then
    if sprite ~= nil then pcall(function() sprite:close() end) end
    error(uuids, 0)
  end
  return sprite, uuids, facts
end

return module
