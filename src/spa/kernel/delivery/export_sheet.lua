-- Fixed Sprite Sheet handler; runtime request files contain data only.
local kernel_protocol_version = 1
local exporter = dofile(assert(app.params.export_sheet_support))
local function execute()
  local file = assert(io.open(app.params.request, "rb"))
  local request = json.decode(file:read("*a"))
  file:close()
  assert(
    request.kernel_protocol_version == kernel_protocol_version,
    "unsupported Kernel Protocol version"
  )
  return exporter.execute(assert(request.payload))
end
local ok, result = pcall(execute)
local response = ok
    and {
      kernel_protocol_version = kernel_protocol_version,
      status = "ok",
      result = result,
    }
  or {
    kernel_protocol_version = kernel_protocol_version,
    status = "error",
    cause = "operation_rejected",
    message = tostring(result),
  }
local file = assert(io.open(app.params.response, "wb"))
assert(file:write(json.encode(response)))
assert(file:close())
