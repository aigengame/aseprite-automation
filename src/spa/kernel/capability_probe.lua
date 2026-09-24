-- Shared runtime capability observations used by the probe and Plan.
local module = {}
local inspection = dofile(app.params.inspection)
local creation = dofile(app.params.creation)
local layer_select = app.params.layer_select and dofile(app.params.layer_select) or nil
local exporter = app.params.export_image_support and dofile(app.params.export_image_support) or nil
local paint = dofile(app.params.paint)
local digest = dofile(app.params.digest)

local function observes_sprite_inspection()
  local open_sprite = nil
  local inspection_path = assert(app.params.inspection_fixture)
  local ok = pcall(function()
    open_sprite = assert(app.open(inspection_path))
    local result = inspection.inspect(open_sprite, {
      "frames",
      "tags",
      "palettes",
      "layers",
      "cels",
      "slices",
      "tilesets",
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
        background_color = { red = 17, green = 34, blue = 51, alpha = 255 },
      },
      staged_sprite_file = capability_path,
      inspection_scope = {
        "frames",
        "tags",
        "palettes",
        "layers",
        "cels",
        "slices",
        "tilesets",
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

local function observes_layer_hierarchy()
  if layer_select == nil then return false end
  local previous = {
    sprite = app.activeSprite,
    layer = app.activeLayer,
    frame = app.activeFrame,
  }
  local sprite = nil
  local ok = pcall(function()
    sprite = Sprite(2, 2, ColorMode.RGB)
    local group = sprite:newGroup()
    group.name = "parent"
    local child = sprite:newLayer()
    child.parent = group
    local chosen = layer_select.resolve(sprite, { layer_path = { 2, 1 } })
    assert(chosen ~= nil and chosen.layer == child)
    sprite.useLayerUuids = true
    local proof_path = app.fs.joinPath(app.params.workspace, "layer-probe.aseprite")
    assert(sprite:saveAs(proof_path))
    local proof = assert(app.open(proof_path))
    local verified_uuids = inspection.persisted_layer_uuids(sprite, proof)
    proof:close()
    local facts = inspection.inspect(sprite, { "layers" }, verified_uuids)
    assert(facts.metadata.use_layer_uuids)
    assert(facts.layers[2].is_group)
    assert(facts.layers[2].children[1].path[2] == 1)
    assert(type(facts.layers[2].children[1].layer_uuid) == "string")
    chosen = layer_select.resolve(
      sprite,
      { layer_uuid = facts.layers[2].children[1].layer_uuid },
      verified_uuids
    )
    assert(chosen ~= nil and chosen.layer == child)
    sprite.useLayerUuids = false
    local without_uuids = inspection.inspect(sprite, { "layers" })
    assert(without_uuids.layers[2].children[1].layer_uuid == json.decode("null"))
    local rejected, code = layer_select.resolve(sprite, { layer_uuid = "runtime-only" })
    assert(rejected == nil and code == "layer_uuid_unpersisted")
    sprite:close()
    sprite = nil
    os.remove(proof_path)
  end)
  if sprite ~= nil then pcall(function() sprite:close() end) end
  if previous.sprite ~= nil and previous.sprite.isValid then
    pcall(function() app.activeSprite = previous.sprite end)
    pcall(function() app.activeLayer = previous.layer end)
    pcall(function() app.activeFrame = previous.frame end)
  end
  return ok
end

local function observes_paint_apply()
  local source_path = assert(app.params.paint_fixture)
  local target_path = app.fs.joinPath(app.params.workspace, "paint-target.aseprite")
  local ok = pcall(function()
    assert(
      digest.fnv1a64("hello") == "a430d84680aabd0b",
      "content digest implementation failed its known-answer check"
    )
    local result = paint.execute({
      source_sprite_file = source_path,
      staged_sprite_file = target_path,
      target = { layer_path = { 1 }, frame_number = 1 },
      patch = {
        coordinate_space = "image-pixel",
        rectangle = { x = 0, y = 0, width = 1, height = 1 },
        runs = {
          {
            x = 0,
            y = 0,
            length = 1,
            color = { kind = "rgba", red = 17, green = 34, blue = 51, alpha = 255 },
          },
        },
      },
      clipping = "reject",
    }, digest)
    assert(result.persisted_reopen_verified)
    assert(result.pixels_written == 1 and result.pixels_changed == 1)
    assert(result.applied_runs[1].color.red == 17)
    assert(result.before_content_digest.value ~= result.after_content_digest.value)
  end)
  pcall(function() os.remove(target_path) end)
  return ok
end

function module.observe()
  local capabilities = { "aseprite_runtime_introspection" }
  local supports_inspection = observes_sprite_inspection()
  if supports_inspection and observes_sprite_creation() then
    capabilities[#capabilities + 1] = "aseprite_sprite_create"
  end
  if supports_inspection then capabilities[#capabilities + 1] = "aseprite_sprite_inspection" end
  if observes_layer_hierarchy() then
    capabilities[#capabilities + 1] = "aseprite_layer_hierarchy"
  end
  if observes_paint_apply() then capabilities[#capabilities + 1] = "aseprite_paint_apply" end
  if exporter ~= nil then
    local ok = pcall(function()
      local fixture = Sprite(1, 1, ColorMode.RGB)
      local source = app.params.capability_sprite
      local output = app.params.workspace .. "/capability.png"
      local rendered = app.params.workspace .. "/capability.rgba"
      assert(fixture:saveAs(source))
      fixture:close()
      local facts = exporter.execute({
        source_sprite_file = source,
        staged_png_file = output,
        staged_rgba_file = rendered,
        frame_number = 1,
        color_mode = "preserve",
        color_profile = "preserve",
        transparency = "preserve",
      })
      assert(facts.width == 1 and facts.height == 1)
      local pixel_file = assert(io.open(rendered, "rb"))
      assert(#pixel_file:read("*a") == 4)
      pixel_file:close()
      local file = assert(io.open(output, "rb"))
      local signature = file:read(8)
      file:close()
      assert(signature == "\137PNG\r\n\26\n")
      os.remove(output)
      os.remove(rendered)
      os.remove(source)
    end)
    if ok then capabilities[#capabilities + 1] = "aseprite_export_image" end
  end
  return capabilities
end

return module
