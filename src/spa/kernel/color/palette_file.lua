-- Native Palette-file interpretation; callers compare independently decoded facts.
local module = {}

function module.entries(palette)
  local entries = {}
  for index = 0, #palette - 1 do
    local color = palette:getColor(index)
    entries[#entries + 1] = {
      index = index,
      color = { red = color.red, green = color.green, blue = color.blue, alpha = color.alpha },
    }
  end
  return entries
end

function module.import(sprite, payload, uuids)
  local frame = tonumber(payload.palette_frame_number)
  local _, owner = dofile(app.params.effective_palette).resolve(sprite, frame)
  if frame > #sprite.frames or owner ~= frame then
    return {
      rejection = {
        code = "palette_change_missing",
        message = "Palette import requires an exact existing Palette Change",
        details = {
          palette_frame_number = payload.palette_frame_number,
          frame_count = #sprite.frames,
        },
      },
    }
  end
  local path = app.params.response .. ".input." .. payload.palette_file.format
  local loaded
  local ok, cause = pcall(function()
    local bytes = payload.palette_file_bytes:gsub(
      "%x%x",
      function(pair) return string.char(tonumber(pair, 16)) end
    )
    local file = assert(io.open(path, "wb"))
    file:write(bytes)
    file:close()
    loaded = Palette { fromFile = path }
    assert(loaded ~= nil and #loaded > 0, "Native loader returned no Palette Entries")
  end)
  os.remove(path)
  if not ok then
    return {
      rejection = {
        code = "palette_file_failed",
        details = {
          path = payload.palette_file.path,
          reason = "native_load_failed",
          message = tostring(cause),
        },
      },
    }
  end
  local palettes = dofile(app.params.palette)
  local transforms = dofile(app.params.palette_transform)
  local existing = palettes.get(sprite, payload.palette_frame_number)
  if existing.rejection then return existing end
  local entries, growth = module.entries(loaded), {}
  for index = #existing.palette.entries + 1, #entries do
    growth[#growth + 1] = entries[index]
  end
  local resized = transforms.resize(sprite, {
    palette_frame_number = payload.palette_frame_number,
    size = tostring(#entries),
    entries = growth,
  }, uuids)
  if resized.rejection then return resized end
  local result = palettes.set(sprite, {
    palette_frame_number = payload.palette_frame_number,
    entries = entries,
  }, uuids)
  if result.rejection then return result end
  local invalid = dofile(app.params.palette_images).invalid_palette_use(
    sprite,
    palettes.get(sprite, frame).palette
  )
  if invalid then
    return {
      rejection = {
        code = "palette_transform_rejected",
        message = "Imported Palette leaves an invalid Indexed Palette use; remap first",
        details = invalid,
      },
    }
  end
  return result
end

return module
