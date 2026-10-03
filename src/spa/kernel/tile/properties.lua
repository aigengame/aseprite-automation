-- One read projection for native Lua property values; no native storage reconstruction.
local module = {}
local point_mt, size_mt = getmetatable(Point(0, 0)), getmetatable(Size(0, 0))
local rectangle_mt = getmetatable(Rectangle(0, 0, 0, 0))
local uuid_mt = getmetatable(Uuid("00000000-0000-0000-0000-000000000000"))

local function observe(value)
  local kind = type(value)
  if kind == "nil" then
    return { kind = "nil" }
  elseif kind == "boolean" or kind == "string" then
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
    local keys, entries = {}, {}
    for key in pairs(value) do
      if type(key) ~= "string" and math.type(key) ~= "integer" then
        return { kind = "unavailable", reason = "unsupported_native_value" }
      end
      keys[#keys + 1] = key
    end
    table.sort(keys, function(a, b)
      if type(a) ~= type(b) then return type(a) < type(b) end
      return a < b
    end)
    for _, key in ipairs(keys) do
      entries[#entries + 1] = { key = observe(key), value = observe(value[key]) }
    end
    return { kind = "table", entries = entries }
  end
  return { kind = "unavailable", reason = "unsupported_native_value" }
end

function module.read(tile, namespaces)
  local result = {}
  for _, namespace in ipairs(namespaces) do
    local properties = tile.properties(namespace)
    local entries = {}
    for name, value in pairs(properties) do
      entries[#entries + 1] = { name = name, value = observe(value) }
    end
    table.sort(entries, function(a, b) return a.name < b.name end)
    result[#result + 1] = { namespace = namespace, entries = entries }
  end
  return result
end

return module
