-- Fixed packaged Layer mutation handler. Runtime files carry data only.
local kernel_protocol_version = 1
local inspection = dofile(app.params.inspection)
local selection = dofile(app.params.layer_select)
local mutation = dofile(app.params.layer_mutation)
local digest = dofile(app.params.digest)
local persistence = dofile(app.params.persistence)
local frame = dofile(app.params.frame)

local function execute()
  local request_file = assert(io.open(app.params.request, "rb"))
  local request = json.decode(request_file:read("*a"))
  request_file:close()
  assert(
    request.kernel_protocol_version == kernel_protocol_version,
    "unsupported Kernel Protocol version"
  )
  return mutation.execute(
    assert(request.payload),
    inspection,
    selection,
    digest,
    persistence,
    frame
  )
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
