-- Fixed packaged Animation handler. Runtime files carry data only.
local kernel_protocol_version = 1
local animation = dofile(assert(app.params.animation))

local function execute()
  local request_file = assert(io.open(app.params.request, "rb"))
  local request = json.decode(request_file:read("*a"))
  request_file:close()
  assert(
    request.kernel_protocol_version == kernel_protocol_version,
    "unsupported Kernel Protocol version"
  )
  return animation.execute(assert(request.payload))
end

local ok, result = pcall(execute)
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
