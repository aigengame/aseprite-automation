-- Fixed Slice mutation handler. Request files contain data only.
local inspection = dofile(app.params.inspection)
local persistence = dofile(app.params.persistence)
local digest = dofile(app.params.digest)
local slice = dofile(app.params.slice)

local function execute()
  local file = assert(io.open(app.params.request, "rb"))
  local request = json.decode(file:read("*a"))
  file:close()
  assert(request.kernel_protocol_version == 1, "unsupported Kernel Protocol version")
  return slice.execute(assert(request.payload), inspection, digest, persistence)
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
