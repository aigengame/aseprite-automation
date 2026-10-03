-- One read projection for native Lua property values; no native storage reconstruction.
local module = {}
local point_mt, size_mt = getmetatable(Point(0, 0)), getmetatable(Size(0, 0))
local rectangle_mt = getmetatable(Rectangle(0, 0, 0, 0))
local uuid_mt = getmetatable(Uuid("00000000-0000-0000-0000-000000000000"))

local observe

local function observe_table(value)
  local entries = {}
  for key, child in pairs(value) do
    local observed_key = observe(key)
    if observed_key.kind == "unavailable" then return observed_key end
    if observed_key.kind ~= "string" and observed_key.kind ~= "integer" then
      return { kind = "unavailable", reason = "unsupported_native_value" }
    end
    entries[#entries + 1] = { key = observed_key, value = observe(child) }
  end
  table.sort(entries, function(a, b)
    if a.key.kind ~= b.key.kind then return a.key.kind < b.key.kind end
    if a.key.kind == "integer" then return tonumber(a.key.value) < tonumber(b.key.value) end
    return a.key.value < b.key.value
  end)
  return { kind = "table", entries = entries }
end

observe = function(value)
  local kind = type(value)
  if kind == "nil" then
    return { kind = "nil" }
  elseif kind == "string" then
    if not utf8.len(value) then return { kind = "unavailable", reason = "non_utf8_string" } end
    return { kind = "string", value = value }
  elseif kind == "boolean" then
    return { kind = kind, value = value }
  elseif kind == "number" then
    if math.type(value) == "integer" then
      return { kind = "integer", value = tostring(value) }
    elseif value ~= value or value == math.huge or value == -math.huge then
      return { kind = "unavailable", reason = "non_finite_number" }
    end
    return { kind = "number", value = value }
  elseif kind == "userdata" then
    local mt = getmetatable(value)
    if mt == point_mt then
      return { kind = "point", x = value.x, y = value.y }
    elseif mt == size_mt then
      return { kind = "size", width = value.width, height = value.height }
    elseif mt == rectangle_mt then
      return {
        kind = "rectangle",
        x = value.x,
        y = value.y,
        width = value.width,
        height = value.height,
      }
    elseif mt == uuid_mt then
      return { kind = "uuid", value = tostring(value) }
    end
  elseif kind == "table" then
    return observe_table(value)
  end
  return { kind = "unavailable", reason = "unsupported_native_value" }
end

function module.read(tile, namespaces)
  local result = {}
  for _, namespace in ipairs(namespaces) do
    result[#result + 1] =
      { namespace = namespace, value = observe_table(tile.properties(namespace)) }
  end
  return result
end

return module
