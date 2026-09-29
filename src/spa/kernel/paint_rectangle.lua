-- Fixed native Rectangle binding; requests carry no tool or executable selection.
local paint = dofile(app.params.native_paint)
local function execute()
  local file = assert(io.open(app.params.request, "rb"))
  local request = json.decode(file:read("*a"))
  file:close()
  assert(request.kernel_protocol_version == 1)
  local tool = request.payload.style == "filled" and "filled_rectangle" or "rectangle"
  return paint.execute(request.payload, tool)
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
