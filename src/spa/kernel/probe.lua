-- Fixed, packaged Kernel Protocol probe. Runtime files carry data, never Lua behavior.
local kernel_protocol_version = 1

local function observes_sprite_inspection()
  local open_sprite = nil
  local ok = pcall(function()
    open_sprite = Sprite(2, 3, ColorMode.RGB)
    assert(open_sprite.width == 2 and open_sprite.height == 3)
    assert(#open_sprite.frames == 1 and #open_sprite.layers == 1)
    local layer = open_sprite.layers[1]
    assert(type(layer.isImage) == "boolean")
    assert(type(layer.isGroup) == "boolean")
    assert(type(layer.isTilemap) == "boolean")
    assert(type(layer.isReference) == "boolean")
    assert(#open_sprite.tags == 0 and #open_sprite.slices == 0)
    assert(#open_sprite.tilesets == 0 and #open_sprite.cels == 1)
    open_sprite:close()
    open_sprite = nil
  end)
  if open_sprite ~= nil then pcall(function() open_sprite:close() end) end
  return ok
end

local function observes_sprite_creation()
  local open_sprite = nil
  local capability_path = assert(app.params.capability_sprite)
  local ok = pcall(function()
    open_sprite = Sprite(2, 3, ColorMode.RGB)
    app.activeSprite = open_sprite
    app.activeLayer = open_sprite.layers[1]
    app.activeFrame = open_sprite.frames[1]
    app.bgColor = Color{ r=17, g=34, b=51, a=255 }
    app.command.BackgroundFromLayer()
    assert(open_sprite.layers[1].isBackground)
    assert(open_sprite:saveAs(capability_path))
    open_sprite:close()
    open_sprite = nil

    open_sprite = assert(app.open(capability_path))
    local layer = open_sprite.layers[1]
    assert(open_sprite.width == 2 and open_sprite.height == 3)
    assert(#open_sprite.frames == 1 and #open_sprite.layers == 1)
    assert(layer.isBackground and not layer.isTransparent)
    local pixel = layer.cels[1].image:getPixel(0, 0)
    assert(app.pixelColor.rgbaR(pixel) == 17)
    assert(app.pixelColor.rgbaG(pixel) == 34)
    assert(app.pixelColor.rgbaB(pixel) == 51)
    assert(app.pixelColor.rgbaA(pixel) == 255)
    open_sprite:close()
    open_sprite = nil
  end)
  if open_sprite ~= nil then pcall(function() open_sprite:close() end) end
  pcall(function() os.remove(capability_path) end)
  return ok
end

local function observed_capabilities()
  local capabilities = { "aseprite_runtime_introspection" }
  local inspection = observes_sprite_inspection()
  if inspection and observes_sprite_creation() then
    capabilities[#capabilities + 1] = "aseprite_sprite_create"
  end
  if inspection then
    capabilities[#capabilities + 1] = "aseprite_sprite_inspection"
  end
  return capabilities
end

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
    verified_prerequisites = {
      "aseprite_scripting",
      "lua_file_io",
      "aseprite_json",
    },
    verified_capabilities = observed_capabilities(),
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
