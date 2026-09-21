-- Fixed, packaged Kernel Protocol probe. Runtime files carry data, never Lua behavior.
local kernel_protocol_version = 1
local inspection = dofile(app.params.support)

local function observes_sprite_inspection()
  local open_sprite = nil
  local inspection_path = assert(app.params.inspection_fixture)
  local ok, slice_keys = pcall(function()
    open_sprite = assert(app.open(inspection_path))
    local result = inspection.inspect(open_sprite, {
      "frames", "tags", "palettes", "layers", "cels", "slices", "tilesets",
    })
    assert(result.metadata.width == 8 and result.metadata.height == 6)
    assert(result.metadata.color_mode == "rgb")
    assert(result.metadata.frame_count == 2 and result.metadata.tag_count == 1)
    assert(result.metadata.palette_count == 1 and result.metadata.layer_count == 3)
    assert(result.metadata.cel_count == #result.cels and result.metadata.cel_count >= 2)
    assert(result.metadata.slice_count == 1)
    assert(result.metadata.tileset_count == 1)
    assert(type(result.metadata.transparent_color_index) == "number")
    assert(result.metadata.grid_bounds.width > 0)
    assert(result.metadata.pixel_ratio.width > 0)
    assert(#result.frames == 2 and result.frames[2].duration_ms == 340)
    assert(#result.tags == 1 and result.tags[1].direction == "ping_pong")
    assert(result.tags[1].color.green == 20)
    assert(#result.palettes == 1 and #result.palettes[1].entries > 0)
    assert(#result.layers == 2)
    local group = nil
    for _, layer in ipairs(result.layers) do
      if layer.name == "body" then group = layer end
    end
    assert(group ~= nil)
    assert(group.name == "body" and group.is_group and not group.is_image)
    assert(group.blend_mode ~= nil and #group.children == 1)
    local child = group.children[1]
    assert(child.name == "outline" and child.is_image and child.is_visible)
    assert(type(child.is_tilemap) == "boolean")
    assert(type(child.is_reference) == "boolean")
    assert(type(child.is_editable) == "boolean")
    assert(type(child.is_continuous) == "boolean")
    assert(type(child.is_collapsed) == "boolean")
    local found_cel = false
    for _, cel in ipairs(result.cels) do
      if cel.opacity == 123 then
        assert(cel.frame_number == 2 and cel.bounds.x == 4)
        assert(cel.z_index == 4)
        found_cel = true
      end
    end
    assert(found_cel)
    assert(#result.tilesets == 1)
    assert(result.tilesets[1].base_index == 7)
    assert(result.tilesets[1].tile_size.width == 4)
    local has_slice_keys = type(result.slices) == "table"
    if has_slice_keys then
      assert(#result.slices == 1 and result.slices[1].name == "panel")
      assert(#result.slices[1].keys > 0)
    end
    open_sprite:close()
    open_sprite = nil
    return has_slice_keys
  end)
  if open_sprite ~= nil then pcall(function() open_sprite:close() end) end
  if not ok then return false, false end
  return true, slice_keys
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
  local supports_inspection, supports_slice_keys = observes_sprite_inspection()
  if supports_inspection and observes_sprite_creation() then
    capabilities[#capabilities + 1] = "aseprite_sprite_create"
  end
  if supports_inspection then
    capabilities[#capabilities + 1] = "aseprite_sprite_inspection"
  end
  if supports_slice_keys then
    capabilities[#capabilities + 1] = "aseprite_sprite_slice_keys"
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
