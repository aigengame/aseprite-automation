-- One packaged operation with a read-only resolution phase before staging/encoding.
local exporter = dofile(app.params.animation_export)
local function execute()
  local file = assert(io.open(app.params.request, "rb"))
  local request = json.decode(file:read("a"))
  file:close()
  assert(request.kernel_protocol_version == 1, "unsupported Kernel Protocol")
  return exporter.execute(request.payload)
end
local ok, result = pcall(execute)
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
