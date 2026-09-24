-- Fixed packaged Cel inspection handler. Runtime files carry data only.
local kernel_protocol_version = 1
local inspection = dofile(app.params.inspection)
local selection = dofile(app.params.layer_select)
local cel = dofile(app.params.cel)
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
  open_sprite = assert(app.open(payload.sprite_file), "could not open Sprite File")
  local uuids = inspection.saved_layer_uuids(open_sprite, payload.sprite_file)
  local address = payload.operation == "get" and payload.target
    or {
      layer = payload.layer,
      frame_number = payload.from_frame,
    }
  local layer, path, rejected = cel.resolve(open_sprite, address, selection, uuids)
  if rejected then return rejected end
  local result
  if payload.operation == "get" then
    result = { cel = cel.inspect(open_sprite, layer, path, address.frame_number) }
  else
    result = cel.list(open_sprite, layer, path, payload.from_frame, payload.to_frame)
  end
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
