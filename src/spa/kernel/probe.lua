-- Fixed, packaged protocol probe. Runtime files carry data, never Lua behavior.
local function execute()
  local request_file = assert(io.open(app.params.request, "rb"))
  local request = json.decode(request_file:read("*a"))
  request_file:close()
  assert(request.protocol_version == 1, "unsupported Kernel Protocol version")
  local echo_file = assert(io.open(app.params.echo, "wb"))
  echo_file:write(json.encode(request)) -- Encode decoded userdata directly.
  echo_file:close()
  return {
    protocol_version = 1,
    status = "ok",
    aseprite_version = tostring(app.version),
    api_version = app.apiVersion,
  }
end

local ok, response = pcall(execute)
if not ok then
  response = { protocol_version = 1, status = "error", message = tostring(response) }
end
local response_file = assert(io.open(app.params.response, "wb"))
response_file:write(json.encode(response))
response_file:close()
