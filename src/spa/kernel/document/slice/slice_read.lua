-- Fixed Slice read handler. Vendor metadata stays inside the Kernel workspace.
local inspection = dofile(app.params.inspection)
local slice = dofile(app.params.slice)
local sprite
local function execute()
  local file = assert(io.open(app.params.request, "rb"))
  local request = json.decode(file:read("*a"))
  file:close()
  assert(request.kernel_protocol_version == 1, "unsupported Kernel Protocol version")
  local payload = request.payload
  sprite = assert(app.open(payload.sprite_file), "could not open Sprite File")
  local snapshot = slice.snapshot(sprite, inspection)
  local index
  if payload.target ~= nil and payload.target ~= json.decode("null") then
    local selected, code, message
    selected, index, code, message = slice.resolve(sprite, payload.target)
    if selected == nil then return { rejection = { code = code, message = message } } end
  end
  return { snapshot = snapshot, selected_index = index }
end
local ok, result = pcall(execute)
if sprite ~= nil then pcall(function() sprite:close() end) end
local response = ok and { kernel_protocol_version = 1, status = "ok", result = result }
  or {
    kernel_protocol_version = 1,
    status = "error",
    cause = "operation_rejected",
    message = tostring(result),
  }
local file = assert(io.open(app.params.response, "wb"))
file:write(json.encode(response))
file:close()
