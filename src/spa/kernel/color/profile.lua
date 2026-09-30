-- Color and Palette owns native profile semantics and observations for all callers.
local module = {}
local inspection = dofile(app.params.inspection)
local persistence = dofile(app.params.persistence)
local digest = dofile(app.params.digest)
local profile_file = dofile(app.params.color_profile_file)
local sections = { "frames", "tags", "palettes", "layers", "cels", "slices", "tilesets" }

local function profile_facts(profile)
  local kind = "icc"
  if profile == ColorSpace() then
    kind = "none"
  elseif profile == ColorSpace { sRGB = true } then
    kind = "srgb"
  end
  return { kind = kind, name = profile.name }
end

function module.restore_file_profile(sprite, path)
  local declared, icc_color_space = profile_file.declared_profile(path)
  -- Headless app.open uses FileOpConfig defaults even after changing preferences.
  -- Restore only an encoded None, through native assignment; never transform stored colors.
  if declared == "none" then sprite:assignColorSpace(ColorSpace()) end
  assert(
    profile_facts(sprite.colorSpace).kind == declared,
    "Loaded Color Profile differs from file"
  )
  return { profile = sprite.colorSpace, icc_color_space = icc_color_space }
end

function module.snapshot(sprite, uuids)
  local document = persistence.snapshot(sprite, inspection, digest, sections, uuids)
  local images, palettes, tilesets = {}, {}, {}
  for index, cel in ipairs(document.sprite.cels) do
    images[index] = {
      layer_path = cel.layer_path,
      frame_number = cel.frame_number,
      content = document.images[index].content,
    }
  end
  for palette_index = 1, #sprite.palettes do
    local palette = sprite.palettes[palette_index]
    local bytes, entries = {}, {}
    for index = 0, #palette - 1 do
      local color = palette:getColor(index)
      entries[index + 1] = string.pack("BBBB", color.red, color.green, color.blue, color.alpha)
      bytes[#bytes + 1] = entries[index + 1]
    end
    palettes[#palettes + 1] = {
      palette_frame_number = palette.frame.frameNumber,
      content = digest.fnv1a64(table.concat(bytes)),
      entries = entries,
    }
  end
  for index = 1, #sprite.tilesets do
    local tileset = sprite.tilesets[index]
    local tiles = {}
    for tile_index = 0, #tileset - 1 do
      tiles[#tiles + 1] =
        { tile_index = tile_index, content = digest.fnv1a64(tileset:tile(tile_index).image.bytes) }
    end
    tilesets[index] = { tileset_index = index, name = tileset.name, tiles = tiles }
  end
  return {
    profile = sprite.colorSpace,
    document = document,
    images = images,
    palettes = palettes,
    tilesets = tilesets,
  }
end

function module.verify_persisted(before, sprite, uuids)
  local after = module.snapshot(sprite, uuids)
  assert(before.profile == after.profile, "Persisted Color Profile differs")
  persistence.assert_equal(before.images, after.images, "Persisted profile Images")
  persistence.assert_equal(before.palettes, after.palettes, "Persisted profile Palettes")
  persistence.assert_equal(before.tilesets, after.tilesets, "Persisted profile Tilesets")
end

local function change(before, after)
  return {
    before_digest = before.content,
    after_digest = after.content,
    changed = before.content ~= after.content,
  }
end

local function requested_profile(input)
  if input.profile.kind == "none" then return ColorSpace() end
  if input.profile.kind == "srgb" then return ColorSpace { sRGB = true } end
  assert(input.profile.kind == "icc", "Unknown Color Profile kind")
  local path = app.params.workspace .. "/profile-input.icc"
  local bytes = input.icc_bytes:gsub(
    "%x%x",
    function(value) return string.char(tonumber(value, 16)) end
  )
  local file = assert(io.open(path, "wb"))
  assert(file:write(bytes))
  file:close()
  local ok, profile = pcall(function() return ColorSpace { fromFile = path } end)
  os.remove(path)
  if not ok or profile_facts(profile).kind ~= "icc" then return nil end
  return profile, bytes:sub(17, 20)
end

function module.apply_live(sprite, operation, input, uuids, profile_state)
  assert(operation == "assign" or operation == "convert", "Unsupported Color Profile operation")
  -- Track only the current native profile's encoded ICC signature. A successful
  -- ColorSpace constructor does not prove that the native converter supports it.
  if operation == "convert" and profile_facts(sprite.colorSpace).kind == "icc" then
    assert(profile_state.profile == sprite.colorSpace, "ICC source profile evidence is stale")
    assert(profile_state.icc_color_space ~= nil, "ICC source color space is unknown")
    if profile_state.icc_color_space ~= "RGB " then
      return {
        rejection = {
          code = "color_profile_source_unsupported",
          details = { icc_color_space = profile_state.icc_color_space:gsub("%s+$", "") },
        },
      }
    end
  end
  local target, icc_color_space = requested_profile(input)
  if target == nil then
    return {
      rejection = {
        code = "color_profile_file_failed",
        details = { path = input.profile.icc_file, reason = "native_load_failed" },
      },
    }
  end
  local before = module.snapshot(sprite, uuids)
  if operation == "assign" then
    sprite:assignColorSpace(target)
  else
    sprite:convertColorSpace(target)
  end
  local after = module.snapshot(sprite, uuids)
  assert(sprite.colorSpace == target, "Effective Color Profile differs from requested profile")
  profile_state.profile = after.profile
  profile_state.icc_color_space = icc_color_space
  if operation == "convert" then
    -- The native operation may change stored Images and Palettes, preserving other document facts.
    before.document.images = after.document.images
    before.document.sprite.palettes = after.document.sprite.palettes
  else
    persistence.assert_equal(before.tilesets, after.tilesets, "Assign Color Profile Tilesets")
  end
  persistence.assert_equal(before.document, after.document, "Color Profile " .. operation)
  local images, palettes, tilesets = {}, {}, {}
  for index, image in ipairs(after.images) do
    local facts = change(before.images[index], image)
    facts.layer_path, facts.frame_number = image.layer_path, image.frame_number
    images[#images + 1] = facts
  end
  for index, palette in ipairs(after.palettes) do
    local facts = change(before.palettes[index], palette)
    facts.palette_frame_number, facts.changed_indexes = palette.palette_frame_number, {}
    for entry, color in ipairs(palette.entries) do
      if before.palettes[index].entries[entry] ~= color then
        facts.changed_indexes[#facts.changed_indexes + 1] = entry - 1
      end
    end
    palettes[#palettes + 1] = facts
  end
  for index, tileset in ipairs(after.tilesets) do
    local facts = { tileset_index = index, name = tileset.name, tiles = {} }
    for tile_index, tile in ipairs(tileset.tiles) do
      local item = change(before.tilesets[index].tiles[tile_index], tile)
      item.tile_index = tile.tile_index
      facts.tiles[#facts.tiles + 1] = item
    end
    tilesets[#tilesets + 1] = facts
  end
  local icc_file = json.decode("null")
  if input.profile.kind == "icc" then
    icc_file = {
      path = input.icc_file.path,
      byte_size = input.icc_file.byte_size,
      sha256 = input.icc_file.sha256,
      native_name = after.profile.name,
      matches_effective_profile = sprite.colorSpace == target,
    }
  end
  return {
    icc_file = icc_file,
    source_profile = profile_facts(before.profile),
    requested_profile = profile_facts(target),
    effective_profile = profile_facts(after.profile),
    profile_changed = before.profile ~= after.profile,
    matches_requested_profile = sprite.colorSpace == target,
    images = images,
    palettes = palettes,
    tilesets = tilesets,
    persisted_reopen_verified = false,
  }
end

return module
