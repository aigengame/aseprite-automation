-- Slice-owned current snapshots and exact live addressing.
local module = {}
local function has_field(value, name)
  for key in pairs(value) do
    if key == name then return true end
  end
  return false
end

local function indexed_snapshot(frame_count, facts)
  for index, slice in ipairs(facts) do
    slice.slice_index = index
    for key_index, key in ipairs(slice.keys) do
      local next_key = slice.keys[key_index + 1]
      key.effective_frame_range = {
        from_frame = key.frame_number,
        to_frame = next_key and next_key.frame_number - 1 or frame_count,
      }
    end
  end
  return { frame_count = frame_count, slices = facts }
end

function module.snapshot(sprite, inspection)
  return indexed_snapshot(#sprite.frames, inspection.inspect(sprite, { "slices" }).slices)
end

function module.resolve(sprite, address)
  if address.slice_index ~= nil then
    local index = address.slice_index
    if index < 1 or index > #sprite.slices then
      return nil, nil, "slice_missing", "Slice index is outside the current snapshot"
    end
    return sprite.slices[index], index
  end
  local selected, index
  for current, slice in ipairs(sprite.slices) do
    if slice.name == address.slice_name then
      if selected ~= nil then
        return nil, nil, "slice_ambiguous", "Slice name matches more than one Slice"
      end
      selected, index = slice, current
    end
  end
  if selected == nil then return nil, nil, "slice_missing", "No Slice matches the address" end
  return selected, index
end

local function rectangle(value) return Rectangle(value.x, value.y, value.width, value.height) end

local function canonical_color(value)
  if value == nil or value.alpha == 0 then return { red = 0, green = 0, blue = 0, alpha = 0 } end
  return { red = value.red, green = value.green, blue = value.blue, alpha = value.alpha }
end

local function rectangle_fact(value)
  if value == nil or value == json.decode("null") then return json.decode("null") end
  return { x = value.x, y = value.y, width = value.width, height = value.height }
end

local function point_fact(value)
  if value == nil then return json.decode("null") end
  return { x = value.x, y = value.y }
end

local function copy(value)
  if type(value) ~= "table" then return value end
  local result = {}
  for key, item in pairs(value) do
    result[key] = copy(item)
  end
  return result
end

local function set_properties(selected, properties)
  if properties.name ~= nil then selected.name = properties.name end
  if properties.data ~= nil then selected.data = properties.data end
  if properties.color ~= nil then
    local color = properties.color
    selected.color = Color { r = color.red, g = color.green, b = color.blue, a = color.alpha }
  end
  if properties.bounds ~= nil then selected.bounds = rectangle(properties.bounds) end
  if has_field(properties, "center") then
    if properties.center == nil or properties.center == json.decode("null") then
      selected.center = nil
    else
      selected.center = rectangle(properties.center)
    end
  end
  if properties.pivot ~= nil then selected.pivot = Point(properties.pivot.x, properties.pivot.y) end
end

local function expected_set(fact, properties)
  local result = copy(fact)
  if properties.name ~= nil then result.name = properties.name end
  if properties.data ~= nil then result.data = properties.data end
  if properties.color ~= nil then result.color = canonical_color(properties.color) end
  if properties.bounds ~= nil then result.keys[1].bounds = rectangle_fact(properties.bounds) end
  if has_field(properties, "center") then
    result.keys[1].center = rectangle_fact(properties.center)
  end
  if properties.pivot ~= nil then result.keys[1].pivot = point_fact(properties.pivot) end
  return result
end

-- Persistence can reorder the native collection. Verify all facts as a multiset,
-- then return only addresses from the reopened collection, never a live index.
function module.execute(payload, inspection, digest, persistence)
  local sprite
  local previous = { sprite = app.activeSprite, layer = app.activeLayer, frame = app.activeFrame }
  local ok, result = pcall(function()
    sprite = assert(app.open(payload.source_sprite_file), "could not open Source Sprite File")
    local sections = { "frames", "tags", "palettes", "layers", "cels", "slices", "tilesets" }
    local uuids = inspection.saved_layer_uuids(sprite, payload.source_sprite_file)
    local before = persistence.snapshot(sprite, inspection, digest, sections, uuids)
    local before_snapshot = module.snapshot(sprite, inspection)
    local selected, selected_index
    local properties = payload.properties
    if payload.operation ~= "add" then
      local code, message
      selected, selected_index, code, message = module.resolve(sprite, payload.target)
      if selected == nil then return { rejection = { code = code, message = message } } end
      local keys = before.sprite.slices[selected_index].keys
      if
        (properties.bounds ~= nil or has_field(properties, "center") or properties.pivot ~= nil)
        and (#keys ~= 1 or keys[1].frame_number ~= 1)
      then
        return {
          rejection = {
            code = "slice_geometry_unsupported",
            message = "Geometry changes require exactly one explicit Slice Key at Frame 1",
          },
        }
      end
    end
    local expected_slices = {}
    for _, fact in ipairs(before.sprite.slices) do
      expected_slices[#expected_slices + 1] = fact
    end
    app.transaction(payload.operation .. " Slice", function()
      if payload.operation == "add" then
        local added = sprite:newSlice(rectangle(properties.bounds))
        set_properties(added, properties)
        expected_slices[#expected_slices + 1] = {
          name = properties.name,
          data = properties.data,
          color = canonical_color(properties.color),
          keys = {
            {
              frame_number = 1,
              bounds = rectangle_fact(properties.bounds),
              center = rectangle_fact(properties.center),
              pivot = point_fact(properties.pivot),
            },
          },
        }
      elseif payload.operation == "set" then
        set_properties(selected, properties)
        expected_slices[selected_index] = expected_set(expected_slices[selected_index], properties)
      elseif payload.operation == "remove" then
        sprite:deleteSlice(selected)
        table.remove(expected_slices, selected_index)
      else
        error("unsupported Slice mutation")
      end
    end)
    local live = persistence.snapshot(sprite, inspection, digest, sections, uuids)
    before.sprite.slices = expected_slices
    before.sprite.metadata.slice_count = #expected_slices
    persistence.assert_same(before, live, "Slice mutation")
    assert(sprite:saveAs(payload.staged_sprite_file), "could not save staged Sprite")
    sprite:close()
    sprite = nil
    sprite = assert(app.open(payload.staged_sprite_file), "could not reopen staged Sprite")
    uuids = inspection.saved_layer_uuids(sprite, payload.staged_sprite_file)
    local reopened = persistence.snapshot(sprite, inspection, digest, sections, uuids)
    persistence.assert_same(live, reopened, "Slice mutation")
    return {
      operation = payload.operation,
      before = before_snapshot,
      selected_before_index = selected_index,
      snapshot = indexed_snapshot(#sprite.frames, reopened.sprite.slices),
      persisted_reopen_verified = true,
    }
  end)
  if sprite ~= nil then pcall(function() sprite:close() end) end
  if previous.sprite ~= nil and previous.sprite.isValid then
    pcall(function() app.activeSprite = previous.sprite end)
    pcall(function() app.activeLayer = previous.layer end)
    pcall(function() app.activeFrame = previous.frame end)
  end
  if not ok then error(result, 0) end
  return result
end

return module
