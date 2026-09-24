-- Fixed packaged Layer inspection handler. Runtime files carry data only.
local kernel_protocol_version = 1
local inspection = dofile(app.params.inspection)
local selection = dofile(app.params.layer_select)
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
  open_sprite = assert(app.open(payload.sprite_file), "could not open Sprite file")
  local verified_uuids = inspection.saved_layer_uuids(open_sprite, payload.sprite_file)
  local selected, code, message = selection.resolve(open_sprite, payload.target, verified_uuids)
  if selected == nil then
    open_sprite:close()
    open_sprite = nil
    return { rejection = { code = code, message = message } }
  end
  local result = {
    selected_path = selected.path,
    sprite = inspection.inspect(open_sprite, { "layers" }, verified_uuids),
  }
  open_sprite:close()
  open_sprite = nil
  return result
end

local ok, result = pcall(execute)
if open_sprite ~= nil then pcall(function() open_sprite:close() end) end
local response
if ok then
  response = { kernel_protocol_version = kernel_protocol_version, status = "ok", result = result }
else
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
