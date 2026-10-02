-- Packaged read-only Tile handler; runtime inputs are data, never Lua source.
local inspection = dofile(app.params.tile_inspection)
local sprite
local function execute()
  local file = assert(io.open(app.params.request, "rb"))
  local request = json.decode(file:read("*a"))
  file:close()
  assert(request.kernel_protocol_version == 1, "unsupported Kernel Protocol version")
  local payload = assert(request.payload)
  sprite = assert(app.open(payload.sprite_file), "could not open Sprite File")
  return inspection.read(sprite, payload)
end
local ok, result = pcall(execute)
if sprite ~= nil then pcall(function() sprite:close() end) end
local response
if ok then
  response = { kernel_protocol_version = 1, status = "ok", result = result }
else
  response = {
    kernel_protocol_version = 1,
    status = "error",
    cause = "operation_rejected",
    message = tostring(result),
  }
end
local file = assert(io.open(app.params.response, "wb"))
file:write(json.encode(response))
file:close()
