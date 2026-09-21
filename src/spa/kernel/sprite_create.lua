-- Fixed packaged Sprite creation handler. Runtime files carry data only.
local kernel_protocol_version = 1
local inspection = dofile(app.params.support)
local open_sprite = nil

local function execute()
  local request_file = assert(io.open(app.params.request, "rb"))
  local request = json.decode(request_file:read("*a"))
  request_file:close()
  assert(request.kernel_protocol_version == kernel_protocol_version,
         "unsupported Kernel Protocol version")
  local payload = assert(request.payload)
  assert(payload.color_mode == "rgb", "unsupported Color Mode")
  assert(type(payload.width) == "number" and type(payload.height) == "number",
         "invalid Sprite dimensions")
  assert(type(payload.staged_sprite_file) == "string", "missing staged Sprite file")
  assert(payload.initial_layer ~= nil, "missing initial Layer choice")

  open_sprite = Sprite(payload.width, payload.height, ColorMode.RGB)
  if payload.initial_layer.kind == "background" then
    local color = assert(payload.initial_layer.background_color)
    app.activeSprite = open_sprite
    app.activeLayer = open_sprite.layers[1]
    app.activeFrame = open_sprite.frames[1]
    app.bgColor = Color{
      r=color.red, g=color.green, b=color.blue, a=color.alpha,
    }
    app.command.BackgroundFromLayer()
  else
    assert(payload.initial_layer.kind == "transparent", "invalid initial Layer choice")
  end

  assert(open_sprite:saveAs(payload.staged_sprite_file), "could not save staged Sprite")
  open_sprite:close()
  open_sprite = nil
  open_sprite = assert(app.open(payload.staged_sprite_file),
                       "could not reopen staged Sprite")
  local sprite = inspection.inspect(open_sprite, payload.inspection_scope)
  open_sprite:close()
  open_sprite = nil
  return { sprite=sprite }
end

local ok, result = pcall(execute)
local response
if ok then
  response = {
    kernel_protocol_version=kernel_protocol_version,
    status="ok",
    result=result,
  }
else
  if open_sprite ~= nil then pcall(function() open_sprite:close() end) end
  response = {
    kernel_protocol_version=kernel_protocol_version,
    status="error",
    cause="operation_rejected",
    message=tostring(result),
  }
end
local response_file = assert(io.open(app.params.response, "wb"))
response_file:write(json.encode(response))
response_file:close()
