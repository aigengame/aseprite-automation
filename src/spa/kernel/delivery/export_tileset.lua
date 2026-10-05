-- Fixed packaged Tileset export; final publication belongs to Application.
local exporter = dofile(assert(app.params.export_tileset_support))
local function execute()
  local file = assert(io.open(app.params.request, "rb"))
  local request = json.decode(file:read("a"))
  file:close()
  assert(request.kernel_protocol_version == 1, "Unsupported Kernel Protocol version")
  return exporter.execute(assert(request.payload))
end
local ok, result = pcall(execute)
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
assert(file:write(json.encode(response)))
assert(file:close())
