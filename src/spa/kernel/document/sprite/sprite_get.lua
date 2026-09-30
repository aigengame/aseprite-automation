-- Fixed packaged Sprite inspection handler. Runtime files carry data only.
local kernel_protocol_version = 1
local inspection = dofile(app.params.inspection)
local open_sprite = nil

local function execute()
  local request_file = assert(io.open(app.params.request, "rb"))
  local request = json.decode(request_file:read("*a"))
  request_file:close()
  assert(
    request.kernel_protocol_version == kernel_protocol_version,
    "unsupported Kernel Protocol version"
  )
  local payload = assert(request.payload)
  assert(type(payload.sprite_file) == "string", "missing Sprite file")
  open_sprite = assert(app.open(payload.sprite_file), "could not open Sprite file")
  local verified_uuids = {}
  for _, section in ipairs(payload.inspection_scope) do
    if section == "layers" then
      verified_uuids = inspection.saved_layer_uuids(open_sprite, payload.sprite_file)
      break
    end
  end
  local sprite = inspection.inspect(open_sprite, payload.inspection_scope, verified_uuids)
  open_sprite:close()
  open_sprite = nil
  return { sprite = sprite }
end

local ok, result = pcall(execute)
local response
if ok then
  response = {
    kernel_protocol_version = kernel_protocol_version,
    status = "ok",
    result = result,
  }
else
  if open_sprite ~= nil then pcall(function() open_sprite:close() end) end
  response = {
    kernel_protocol_version = kernel_protocol_version,
    status = "error",
    cause = "operation_rejected",
    message = tostring(result),
  }
end
local response_file = assert(io.open(app.params.response, "wb"))
response_file:write(json.encode(response))
response_file:close()
