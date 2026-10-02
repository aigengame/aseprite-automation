-- Complete native Slice observation. Exported vendor data stays in the workspace.
local module = {}
local json_null = json.decode("null")

local function json_kind(value, prefix)
  return type(value) == "userdata" and tostring(value):sub(1, 1) == prefix
end

local function has_field(value, name)
  for key in pairs(value) do
    if key == name then return true end
  end
  return false
end

local function integer(value, minimum, maximum)
  return type(value) == "number" and value >= minimum and value <= maximum and value % 1 == 0
end

local function coordinate(value) return integer(value, -2147483648, 2147483647) end

local function rectangle(value)
  assert(json_kind(value, "{"), "Slice Key Rectangle is not an object")
  assert(coordinate(value.x) and coordinate(value.y), "Slice Key Rectangle has invalid coordinates")
  assert(
    integer(value.w, 0, 2147483647) and integer(value.h, 0, 2147483647),
    "Slice Key Rectangle has invalid dimensions"
  )
  return { x = value.x, y = value.y, width = value.w, height = value.h }
end

local function point(value)
  assert(json_kind(value, "{"), "Slice Key Point is not an object")
  assert(coordinate(value.x) and coordinate(value.y), "Slice Key Point has invalid coordinates")
  return { x = value.x, y = value.y }
end

local function matches_rectangle(fact, native)
  if native == nil then return fact == json_null end
  return fact ~= json_null
    and fact.x == native.x
    and fact.y == native.y
    and fact.width == native.width
    and fact.height == native.height
end

local function matches_point(fact, native)
  if native == nil then return fact == json_null end
  return fact ~= json_null and fact.x == native.x and fact.y == native.y
end

local function rgba(color)
  return { red = color.red, green = color.green, blue = color.blue, alpha = color.alpha }
end

local function vendor_color(value)
  assert(
    type(value) == "string" and value:match("^#%x%x%x%x%x%x%x%x$"),
    "Slice vendor color is not RGBA hexadecimal"
  )
  return {
    red = tonumber(value:sub(2, 3), 16),
    green = tonumber(value:sub(4, 5), 16),
    blue = tonumber(value:sub(6, 7), 16),
    alpha = tonumber(value:sub(8, 9), 16),
  }
end

local function read_file(path)
  local file = assert(io.open(path, "rb"), "could not open Slice vendor data")
  local payload = file:read("*a")
  file:close()
  return payload
end

local function restore_editor_state(previous)
  if previous.sprite ~= nil and previous.sprite.isValid then
    pcall(function() app.activeSprite = previous.sprite end)
    pcall(function() app.activeLayer = previous.layer end)
    pcall(function() app.activeFrame = previous.frame end)
  end
end

function module.inspect(sprite)
  if #sprite.slices == 0 then return {} end
  local workspace = assert(app.params.workspace, "missing Kernel workspace")
  local data_path = workspace .. "/sprite-slices.json"
  -- A command can return without writing. Never reuse an earlier observation.
  os.remove(data_path)
  local stale = io.open(data_path, "rb")
  if stale then
    stale:close()
    error("could not clear previous Slice vendor data")
  end
  local previous = { sprite = app.activeSprite, layer = app.activeLayer, frame = app.activeFrame }
  local exported, failure = pcall(function()
    app.activeSprite = sprite
    app.command.ExportSpriteSheet {
      ui = false,
      recent = false,
      askOverwrite = false,
      type = SpriteSheetType.HORIZONTAL,
      textureFilename = "",
      dataFilename = data_path,
      dataFormat = SpriteSheetDataFormat.JSON_HASH,
      openGenerated = false,
      listLayers = false,
      listTags = false,
      listSlices = true,
      layer = "",
      tag = "",
      splitLayers = false,
      splitTags = false,
      splitGrid = false,
      fromTilesets = false,
      ignoreEmpty = false,
      trim = false,
      trimSprite = false,
      trimByGrid = false,
      extrude = false,
      mergeDuplicates = false,
      powerOfTwoSize = false,
      borderPadding = 0,
      shapePadding = 0,
      innerPadding = 0,
    }
  end)
  restore_editor_state(previous)
  if not exported then error(failure) end

  local vendor = json.decode(read_file(data_path))
  assert(
    json_kind(vendor, "{") and json_kind(vendor.meta, "{"),
    "Slice vendor data has no metadata object"
  )
  local entries = vendor.meta.slices
  assert(json_kind(entries, "["), "Slice vendor data has no Slice array")
  assert(#entries == #sprite.slices, "Slice vendor count differs from the opened Sprite")
  local slices = {}
  for index = 1, #sprite.slices do
    local native = sprite.slices[index]
    local value = entries[index]
    assert(json_kind(value, "{"), "Slice vendor entry is not an object")
    assert(
      type(value.name) == "string" and value.name == native.name,
      "Slice vendor order differs from the opened Sprite"
    )
    local data = ""
    if has_field(value, "data") then
      assert(type(value.data) == "string", "Slice vendor user data is not a string")
      data = value.data
    end
    assert(data == native.data, "Slice vendor user data differs from the opened Sprite")
    local color = { red = 0, green = 0, blue = 0, alpha = 0 }
    if has_field(value, "color") then color = vendor_color(value.color) end
    local native_color = rgba(native.color)
    assert(
      color.red == native_color.red
        and color.green == native_color.green
        and color.blue == native_color.blue
        and color.alpha == native_color.alpha,
      "Slice vendor color differs from the opened Sprite"
    )
    if has_field(value, "properties") then
      assert(json_kind(value.properties, "{"), "Slice vendor properties are not an object")
    end
    local keys = {}
    if has_field(value, "keys") then
      assert(json_kind(value.keys, "["), "Slice vendor Keys are not an array")
      local previous_frame = -1
      for key_index = 1, #value.keys do
        local key = value.keys[key_index]
        assert(json_kind(key, "{"), "Slice Key vendor entry is not an object")
        assert(
          integer(key.frame, 0, #sprite.frames - 1) and key.frame > previous_frame,
          "Slice Key has an invalid or unordered Frame"
        )
        previous_frame = key.frame
        keys[#keys + 1] = {
          frame_number = key.frame + 1,
          bounds = rectangle(key.bounds),
          center = has_field(key, "center") and rectangle(key.center) or json_null,
          pivot = has_field(key, "pivot") and point(key.pivot) or json_null,
        }
      end
    end
    if #keys == 0 then
      assert(native.bounds == nil, "Slice vendor entry has no explicit Keys")
    else
      -- Public Lua exposes the first explicit Key even when another Frame is
      -- active. Cross-check that available observation; later Keys still come
      -- from the native export, with shape/order/range validation above.
      local first = keys[1]
      assert(
        matches_rectangle(first.bounds, native.bounds)
          and matches_rectangle(first.center, native.center)
          and matches_point(first.pivot, native.pivot),
        "Slice vendor first Key differs from the opened Sprite"
      )
    end
    slices[#slices + 1] = { name = value.name, data = data, color = color, keys = keys }
  end
  return slices
end

return module
