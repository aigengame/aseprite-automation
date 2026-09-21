-- Fixed, packaged Kernel Protocol probe. Runtime files carry data, never Lua behavior.
local kernel_protocol_version = 1

local function execute()
  local request_file = assert(io.open(app.params.request, "rb"))
  local request = json.decode(request_file:read("*a"))
  request_file:close()
  assert(
    request.kernel_protocol_version == kernel_protocol_version,
    "unsupported Kernel Protocol version"
  )
  local echo_file = assert(io.open(app.params.echo, "wb"))
  echo_file:write(json.encode(request)) -- Encode decoded userdata directly.
  echo_file:close()
  return {
    kernel_protocol_version = kernel_protocol_version,
    status = "ok",
    aseprite_version = tostring(app.version),
    api_version = app.apiVersion,
    lua_version = _VERSION,
    verified_capabilities = {
      "aseprite_scripting",
      "lua_file_io",
      "aseprite_json",
    },
  }
end

local ok, response = pcall(execute)
if not ok then
  response = {
    kernel_protocol_version = kernel_protocol_version,
    status = "error",
    message = tostring(response),
  }
end
local response_file = assert(io.open(app.params.response, "wb"))
response_file:write(json.encode(response))
response_file:close()
