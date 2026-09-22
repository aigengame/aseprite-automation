-- Fixed, packaged Kernel Protocol probe. Runtime files carry data, never Lua behavior.
local kernel_protocol_version = 1
local inspection = dofile(app.params.inspection)
local creation = dofile(app.params.creation)

local function observes_sprite_inspection()
  local open_sprite = nil
  local inspection_path = assert(app.params.inspection_fixture)
  local ok = pcall(function()
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
    assert(#result.slices == 1 and result.slices[1].name == "panel")
    assert(result.slices[1].data == "panel-data")
    assert(#result.slices[1].keys == 1)
    assert(result.slices[1].keys[1].frame_number == 1)
    open_sprite:close()
    open_sprite = nil
  end)
  if open_sprite ~= nil then pcall(function() open_sprite:close() end) end
  return ok
end

local function observes_sprite_creation()
  local capability_path = assert(app.params.capability_sprite)
  local ok = pcall(function()
    local result = creation.execute({
      width = 2,
      height = 3,
      color_mode = "rgb",
      initial_layer = {
        kind = "background",
        background_color = { red=17, green=34, blue=51, alpha=255 },
      },
      staged_sprite_file = capability_path,
      inspection_scope = {
        "frames", "tags", "palettes", "layers", "cels", "slices", "tilesets",
      },
    }, inspection)
    assert(result.sprite.metadata.width == 2 and result.sprite.metadata.height == 3)
    assert(result.sprite.metadata.frame_count == 1)
    assert(result.sprite.metadata.layer_count == 1)
    assert(result.sprite.layers[1].is_background)
    assert(not result.sprite.layers[1].is_transparent)
    assert(result.persisted_initial_layer.kind == "background")
    assert(result.persisted_initial_layer.background_color.red == 17)
    assert(result.persisted_initial_layer.background_color.green == 34)
    assert(result.persisted_initial_layer.background_color.blue == 51)
    assert(result.persisted_initial_layer.background_color.alpha == 255)
  end)
  pcall(function() os.remove(capability_path) end)
  return ok
end

local function observed_capabilities()
  local capabilities = { "aseprite_runtime_introspection" }
  local supports_inspection = observes_sprite_inspection()
  if supports_inspection and observes_sprite_creation() then
    capabilities[#capabilities + 1] = "aseprite_sprite_create"
  end
  if supports_inspection then
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
