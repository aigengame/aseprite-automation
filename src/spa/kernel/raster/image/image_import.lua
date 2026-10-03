-- Fixed native insertion of a frozen, independently decoded compatible PNG.
local inspection = dofile(app.params.inspection)
local selection = dofile(app.params.layer_select)
local cels = dofile(app.params.cel)
local persistence = dofile(app.params.persistence)
local profiles = dofile(app.params.color_profile)
local palettes = dofile(app.params.effective_palette)
local digest = dofile(app.params.digest)
local null = json.decode("null")
local sprite, raster = nil, nil
local previous = { sprite = app.activeSprite, layer = app.activeLayer, frame = app.activeFrame }

local function bytes(hex)
  return (hex:gsub("%x%x", function(value) return string.char(tonumber(value, 16)) end))
end

local function reject(input, reason, message)
  return {
    rejection = {
      code = "image_import_incompatible",
      details = {
        path = input.raster_path,
        reason = reason,
        message = message,
      },
    },
  }
end

local function profile_fact(state)
  return { kind = state.kind, icc_identity = state.icc_identity or null }
end

local function same_profile(state, expected)
  return state.kind == expected.kind
    and (state.kind ~= "icc" or state.icc_identity == expected.icc_identity)
end

-- Observe stored channels or indexes, then their literal Indexed RGBA meaning.
-- A regular Layer's mask index decodes to transparent black in the native path.
local function content(image, owner, frame_number, background)
  local stored, rgba, used = {}, {}, {}
  local palette, palette_frame = palettes.resolve(owner, frame_number)
  local pc = app.pixelColor
  for y = 0, image.height - 1 do
    for x = 0, image.width - 1 do
      local pixel = image:getPixel(x, y)
      if image.colorMode == ColorMode.RGB then
        local value =
          string.pack("BBBB", pc.rgbaR(pixel), pc.rgbaG(pixel), pc.rgbaB(pixel), pc.rgbaA(pixel))
        stored[#stored + 1], rgba[#rgba + 1] = value, value
      else
        assert(image.colorMode == ColorMode.INDEXED, "Unsupported import Color Mode")
        if palette == nil or pixel >= #palette then return nil end
        local color = palette:getColor(pixel)
        stored[#stored + 1] = string.char(pixel)
        rgba[#rgba + 1] = (not background and pixel == owner.transparentColor)
            and string.rep("\0", 4)
          or string.pack("BBBB", color.red, color.green, color.blue, color.alpha)
        used[pixel] = true
      end
    end
  end
  local basis = null
  if image.colorMode == ColorMode.INDEXED then
    local indexes = {}
    for index = 0, 255 do
      if used[index] then
        local color = palette:getColor(index)
        indexes[#indexes + 1] = {
          index = index,
          color = {
            red = color.red,
            green = color.green,
            blue = color.blue,
            alpha = color.alpha,
          },
        }
      end
    end
    basis = {
      frame_number = frame_number,
      palette_frame_number = palette_frame,
      palette_size = #palette,
      indexes = indexes,
    }
  end
  return table.concat(stored), table.concat(rgba), basis
end

local function image_fact(image, mode, stored, rgba)
  return {
    width = image.width,
    height = image.height,
    color_mode = mode,
    stored_content_digest = { algorithm = "fnv1a64", value = digest.fnv1a64(stored) },
    rgba_content_digest = { algorithm = "fnv1a64", value = digest.fnv1a64(rgba) },
  }
end

local function without_created(snapshot, index)
  table.remove(snapshot.document.sprite.cels, index)
  table.remove(snapshot.document.images, index)
  table.remove(snapshot.images, index)
  snapshot.document.sprite.metadata.cel_count = snapshot.document.sprite.metadata.cel_count - 1
  for _, link in ipairs(snapshot.document.links) do
    for side = 1, 2 do
      assert(link[side] ~= index, "Imported Image is unexpectedly shared")
      if link[side] > index then link[side] = link[side] - 1 end
    end
  end
  return snapshot
end

local function execute()
  local file = assert(io.open(app.params.request, "rb"))
  local request = json.decode(file:read("a"))
  file:close()
  assert(request.kernel_protocol_version == 1, "Unsupported Kernel Protocol")
  local input = request.payload
  sprite = assert(app.open(input.source_sprite_file), "Could not open Source Sprite File")
  local uuids = inspection.saved_layer_uuids(sprite, input.source_sprite_file)
  local layer, path, refused = cels.resolve(sprite, input.target, selection, uuids)
  if refused then return refused end
  local number = input.target.frame_number
  refused = cels.prevalidate(sprite, layer, number, "add", nil, nil)
  if refused then return refused end
  local decoded = input.decoded
  local expected_mode = decoded.color_mode == "rgb" and ColorMode.RGB or ColorMode.INDEXED
  if sprite.colorMode ~= expected_mode then
    return reject(input, "color_mode", "PNG and Sprite Color Modes differ")
  end
  local profile_ok, target_profile =
    pcall(profiles.restore_file_profile, sprite, input.source_sprite_file)
  if not profile_ok then
    return reject(input, "color_profile", "Source Sprite profile cannot be restored")
  end
  if not same_profile(target_profile, decoded.profile) then
    return reject(input, "color_profile", "PNG and destination Color Profile identities differ")
  end
  local input_bytes = bytes(input.raster_bytes)
  local private_png = app.params.workspace .. "/import-input.png"
  local output = assert(io.open(private_png, "wb"))
  assert(output:write(input_bytes))
  assert(output:close())
  local check = assert(io.open(private_png, "rb"))
  assert(check:read("a") == input_bytes, "Private PNG differs from frozen input")
  check:close()
  local loaded, opened = pcall(app.open, private_png)
  if loaded then raster = opened end
  if raster == nil then
    return reject(input, "native_load", "Aseprite could not load the frozen PNG")
  end
  local restored, raster_profile = pcall(
    profiles.restore_declared_profile,
    raster,
    decoded.profile.kind,
    type(decoded.icc_bytes) == "string" and bytes(decoded.icc_bytes) or nil
  )
  if
    not restored
    or raster.colorSpace ~= sprite.colorSpace
    or not same_profile(raster_profile, decoded.profile)
  then
    return reject(input, "color_profile", "Native PNG loading changed encoded profile meaning")
  end
  if #raster.frames ~= 1 or #raster.cels ~= 1 or raster.colorMode ~= expected_mode then
    return reject(input, "native_content", "Native PNG structure differs from the decoded input")
  end
  local source_cel = raster.cels[1]
  local image = source_cel.image
  if image.width ~= decoded.width or image.height ~= decoded.height then
    return reject(input, "native_content", "Native PNG Image dimensions differ")
  end
  local expected_stored, expected_rgba = bytes(decoded.stored_bytes), bytes(decoded.rgba_bytes)
  local stored, rgba = content(image, raster, 1, source_cel.layer.isBackground)
  if stored ~= expected_stored or rgba ~= expected_rgba then
    return reject(input, "native_content", "Native PNG pixels differ from independent decoding")
  end
  local target_stored, target_rgba = content(image, sprite, number, false)
  if target_stored ~= expected_stored or target_rgba ~= expected_rgba then
    return reject(
      input,
      "palette",
      "Destination Palette or mask changes a used index's RGBA meaning"
    )
  end
  local before = cels.inspect(sprite, layer, path, number)
  local original = profiles.snapshot(sprite, uuids)
  local count = #sprite.cels
  local created = nil
  app.transaction("Import compatible PNG", function()
    created = sprite:newCel(layer, number, image, Point(input.position.x, input.position.y))
    assert(#sprite.cels == count + 1, "Import changed unexpected Cel count")
    for _, other in ipairs(sprite.cels) do
      assert(other == created or other.image ~= created.image, "Imported Image is shared")
    end
    assert(created.opacity == 255 and created.zIndex == 0, "Unexpected new-Cel defaults")
    assert(
      created.position.x == input.position.x and created.position.y == input.position.y,
      "Imported position narrowed"
    )
    local current_stored, current_rgba = content(created.image, sprite, number, false)
    assert(
      current_stored == expected_stored and current_rgba == expected_rgba,
      "Insertion changed PNG content"
    )
    local created_index = nil
    for index, cel in ipairs(sprite.cels) do
      if cel == created then created_index = index end
    end
    persistence.assert_equal(
      original,
      without_created(profiles.snapshot(sprite, uuids), assert(created_index)),
      "Unrelated import facts"
    )
  end)
  raster:close()
  raster = nil
  local live = profiles.snapshot(sprite, uuids)
  assert(sprite:saveAs(input.staged_sprite_file), "Could not save imported Sprite")
  sprite:close()
  sprite = assert(app.open(input.staged_sprite_file), "Could not reopen imported Sprite")
  local reopened_profile = profiles.restore_file_profile(sprite, input.staged_sprite_file)
  local reopened_uuids = inspection.saved_layer_uuids(sprite, input.staged_sprite_file)
  profiles.verify_persisted(live, sprite, reopened_uuids)
  local persisted = profiles.snapshot(sprite, reopened_uuids)
  persistence.assert_same(live.document, persisted.document, "PNG import")
  local selected = assert(selection.resolve(sprite, { layer_path = path }, reopened_uuids))
  local after = cels.inspect(sprite, selected.layer, path, number)
  local reopened_image = assert(selected.layer:cel(number)).image
  local reopened_stored, reopened_rgba, palette = content(reopened_image, sprite, number, false)
  assert(
    reopened_stored == expected_stored and reopened_rgba == expected_rgba,
    "Persisted PNG pixels differ"
  )
  assert(#after.linked_cels == 0, "Persisted import shares an Image")
  return {
    before = before,
    before_cel_count = count,
    cel = after,
    image = image_fact(reopened_image, decoded.color_mode, reopened_stored, reopened_rgba),
    color_profile = profile_fact(reopened_profile),
    effective_palette = palette,
    transparent_index = expected_mode == ColorMode.INDEXED and sprite.transparentColor or null,
    sprite = persisted.document.sprite,
    persisted_reopen_verified = true,
  }
end

local ok, result = pcall(execute)
if raster ~= nil then pcall(function() raster:close() end) end
if sprite ~= nil then pcall(function() sprite:close() end) end
if previous.sprite ~= nil and previous.sprite.isValid then
  pcall(function() app.activeSprite = previous.sprite end)
  pcall(function() app.activeLayer = previous.layer end)
  pcall(function() app.activeFrame = previous.frame end)
end
local response = ok and { kernel_protocol_version = 1, status = "ok", result = result }
  or {
    kernel_protocol_version = 1,
    status = "error",
    cause = "operation_rejected",
    message = tostring(result),
  }
local output = assert(io.open(app.params.response, "wb"))
output:write(json.encode(response))
output:close()
