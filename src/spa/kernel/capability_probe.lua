-- Shared runtime capability observations used by the probe and Plan.
local module = {}
local inspection = dofile(app.params.inspection)
local creation = dofile(app.params.creation)
local layer_select = app.params.layer_select and dofile(app.params.layer_select) or nil
local exporter = app.params.export_image_support and dofile(app.params.export_image_support) or nil
local paint = dofile(app.params.paint)
local digest = dofile(app.params.digest)
local frame = app.params.frame and dofile(app.params.frame) or nil
local cel_support = app.params.cel and dofile(app.params.cel) or nil
local image_resize_transform = app.params.image_resize_transform
    and dofile(app.params.image_resize_transform)
  or nil
local image_orientation_transform = app.params.image_orientation_transform
    and dofile(app.params.image_orientation_transform)
  or nil

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
    local verified_uuids = inspection.saved_layer_uuids(sprite, proof_path)
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

local function observes_layer_mutation()
  local sprite = nil
  local proof_path = app.fs.joinPath(app.params.workspace, "layer-mutation-probe.aseprite")
  local previous = { sprite = app.activeSprite, layer = app.activeLayer, frame = app.activeFrame }
  local ok = pcall(function()
    sprite = Sprite(2, 2, ColorMode.RGB)
    local lower = sprite.layers[1]
    local lower_name = lower.name
    local upper = sprite:newLayer()
    upper.name = "upper"
    upper.isVisible = false
    upper.isEditable = false
    upper.opacity = 128
    upper.blendMode = BlendMode.MULTIPLY
    assert(not upper.isVisible and not upper.isEditable)
    assert(upper.opacity == 128 and upper.blendMode == BlendMode.MULTIPLY)
    upper.stackIndex = 1
    assert(upper.stackIndex == 1 and lower.stackIndex == 2)
    sprite:deleteLayer(upper)
    assert(#sprite.layers == 1 and sprite.layers[1] == lower)
    assert(sprite:saveAs(proof_path))
    sprite:close()
    sprite = assert(app.open(proof_path))
    assert(#sprite.layers == 1 and sprite.layers[1].name == lower_name)
    sprite:close()
    sprite = nil
  end)
  if sprite ~= nil then pcall(function() sprite:close() end) end
  pcall(function() os.remove(proof_path) end)
  if previous.sprite ~= nil and previous.sprite.isValid then
    pcall(function() app.activeSprite = previous.sprite end)
    pcall(function() app.activeLayer = previous.layer end)
    pcall(function() app.activeFrame = previous.frame end)
  end
  return ok
end

local function observes_layer_merge()
  local sprite = nil
  local proof_path = app.fs.joinPath(app.params.workspace, "layer-merge-probe.aseprite")
  local previous = {
    sprite = app.activeSprite,
    layer = app.activeLayer,
    frame = app.activeFrame,
    new_blend = app.preferences.experimental.new_blend,
  }
  local ok = pcall(function()
    sprite = Sprite(2, 2, ColorMode.RGB)
    local lower = sprite.layers[1]
    lower.name = "lower"
    lower:cel(1).image:putPixel(0, 0, app.pixelColor.rgba(0, 0, 255, 255))
    local upper = sprite:newLayer()
    upper.name = "upper"
    local image = Image(2, 2, ColorMode.RGB)
    image:putPixel(0, 0, app.pixelColor.rgba(255, 0, 0, 128))
    sprite:newCel(upper, 1, image)
    app.activeSprite = sprite
    app.activeLayer = upper
    app.activeFrame = sprite.frames[1]
    app.preferences.experimental.new_blend = true
    assert(app.command.MergeDownLayer())
    assert(#sprite.layers == 1 and sprite.layers[1] == lower)
    assert(sprite:saveAs(proof_path))
    sprite:close()
    sprite = assert(app.open(proof_path))
    assert(#sprite.layers == 1 and sprite.layers[1].name == "lower")
    assert(sprite.layers[1]:cel(1) ~= nil)
    sprite:close()
    sprite = nil
  end)
  if sprite ~= nil then pcall(function() sprite:close() end) end
  pcall(function() os.remove(proof_path) end)
  pcall(function() app.preferences.experimental.new_blend = previous.new_blend end)
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

local function observes_background_conversion()
  local sprite = nil
  local previous = {
    sprite = app.activeSprite,
    layer = app.activeLayer,
    frame = app.activeFrame,
    background_color = app.bgColor,
  }
  local ok = pcall(function()
    sprite = Sprite(2, 2, ColorMode.RGB)
    app.activeSprite = sprite
    local layer = sprite.layers[1]
    app.activeLayer = layer
    app.activeFrame = sprite.frames[1]
    app.bgColor = Color { r = 17, g = 34, b = 51, a = 255 }
    assert(app.command.BackgroundFromLayer())
    assert(layer.isBackground and layer:cel(1) ~= nil)
    assert(app.command.LayerFromBackground())
    assert(layer.isTransparent and not layer.isBackground)
    sprite:close()
    sprite = nil
  end)
  if sprite ~= nil then pcall(function() sprite:close() end) end
  pcall(function() app.bgColor = previous.background_color end)
  if previous.sprite ~= nil and previous.sprite.isValid then
    pcall(function() app.activeSprite = previous.sprite end)
    pcall(function() app.activeLayer = previous.layer end)
    pcall(function() app.activeFrame = previous.frame end)
  end
  return ok
end

local function observes_frame_authoring()
  if frame == nil then return false end
  local sprite = nil
  local previous = { sprite = app.activeSprite, layer = app.activeLayer, frame = app.activeFrame }
  local ok = pcall(function()
    sprite = Sprite(2, 2, ColorMode.RGB)
    local duplicated = frame.apply_live(sprite, "duplicate", {
      source_frame_number = 1,
      cel_mode = "copy",
      duration_ms = 340,
    })
    assert(duplicated.inserted_frame.frame_number == 2)
    assert(duplicated.inserted_frame.duration_ms == 340)
    local added = frame.apply_live(sprite, "add", { frame_number = 1, duration_ms = 1 })
    assert(added.inserted_frame.frame_number == 1)
    assert(added.inserted_frame.duration_ms == 1)
    sprite:close()
    sprite = nil
  end)
  if sprite ~= nil then pcall(function() sprite:close() end) end
  if previous.sprite ~= nil and previous.sprite.isValid then
    pcall(function() app.activeSprite = previous.sprite end)
    pcall(function() app.activeLayer = previous.layer end)
    pcall(function() app.activeFrame = previous.frame end)
  end
  return ok
end

local function observes_frame_editing()
  if frame == nil then return false end
  local sprite = nil
  local previous = { sprite = app.activeSprite, layer = app.activeLayer, frame = app.activeFrame }
  local ok = pcall(function()
    sprite = Sprite(2, 2, ColorMode.RGB)
    sprite:newEmptyFrame(2)
    sprite:newEmptyFrame(3)
    frame.apply_live(sprite, "set", { frame_number = 1, duration_ms = 250 })
    assert(math.floor(sprite.frames[1].duration * 1000 + 0.5) == 250)
    frame.apply_live(sprite, "move", { source_frame_number = 1, target_frame_number = 3 })
    assert(math.floor(sprite.frames[3].duration * 1000 + 0.5) == 250)
    assert(sprite.layers[1]:cel(3) ~= nil)
    frame.apply_live(sprite, "remove", { frame_number = 2 })
    assert(#sprite.frames == 2 and sprite.layers[1]:cel(2) ~= nil)
    sprite:close()
    sprite = nil
  end)
  if sprite ~= nil then pcall(function() sprite:close() end) end
  if previous.sprite ~= nil and previous.sprite.isValid then
    pcall(function() app.activeSprite = previous.sprite end)
    pcall(function() app.activeLayer = previous.layer end)
    pcall(function() app.activeFrame = previous.frame end)
  end
  return ok
end

local function observes_cel_lifecycle()
  if cel_support == nil or layer_select == nil then return false end
  local sprite = nil
  local previous = { sprite = app.activeSprite, layer = app.activeLayer, frame = app.activeFrame }
  local ok = pcall(function()
    sprite = Sprite(2, 2, ColorMode.RGB)
    sprite:newEmptyFrame(2)
    local input = { target = { layer = { layer_path = { 1 } }, frame_number = 2 } }
    local added = cel_support.add_live(sprite, input, layer_select, {})
    assert(not added.before.exists and added.cel.exists)
    local layer = sprite.layers[1]
    assert(cel_support.prevalidate(sprite, layer, 2, "clear", nil, nil) == nil)
    cel_support.apply(sprite, layer, 2, "clear", nil, nil)
    assert(cel_support.inspect(sprite, layer, { 1 }, 2).content == "transparent")
    assert(cel_support.prevalidate(sprite, layer, 2, "remove", nil, nil) == nil)
    cel_support.apply(sprite, layer, 2, "remove", nil, nil)
    assert(not cel_support.inspect(sprite, layer, { 1 }, 2).exists)
    sprite:close()
    sprite = nil
  end)
  if sprite ~= nil then pcall(function() sprite:close() end) end
  if previous.sprite ~= nil and previous.sprite.isValid then
    pcall(function() app.activeSprite = previous.sprite end)
    pcall(function() app.activeLayer = previous.layer end)
    pcall(function() app.activeFrame = previous.frame end)
  end
  return ok
end

local function observes_cel_relationships()
  if cel_support == nil or layer_select == nil then return false end
  local sprite = nil
  local previous = { sprite = app.activeSprite, layer = app.activeLayer, frame = app.activeFrame }
  local ok = pcall(function()
    sprite = Sprite(2, 2, ColorMode.RGB)
    local layer = sprite.layers[1]
    sprite:newEmptyFrame(2)
    sprite:newEmptyFrame(3)
    local original = assert(layer:cel(1))
    local resolved, path = cel_support.resolve(
      sprite,
      { layer = { layer_path = { 1 } }, frame_number = 1 },
      layer_select,
      {}
    )
    assert(resolved == layer and path[1] == 1)
    assert(cel_support.is_regular_transparent(layer))
    assert(cel_support.inspect(sprite, layer, path, 1).exists)
    assert(#cel_support.affected(sprite, original.image) == 1)
    original.position = Point(1, 0)
    original.opacity = 200
    original.zIndex = 1
    local other = sprite:newLayer()
    local duplicate = sprite:newCel(other, 2, original.image, original.position)
    assert(duplicate.image ~= original.image)
    sprite:newEmptyFrame(2)
    app.activeSprite = sprite
    app.activeLayer = layer
    app.activeFrame = sprite.frames[1]
    app.command.NewFrame { content = "cellinked" }
    local linked = assert(layer:cel(2))
    assert(linked.image == original.image)
    assert(#cel_support.affected(sprite, original.image) == 2)
    linked.frameNumber = 4
    sprite:deleteFrame(2)
    linked = assert(layer:cel(3))
    assert(linked.image == original.image)
    app.activeFrame = sprite.frames[3]
    app.command.UnlinkCel()
    assert(layer:cel(3).image ~= original.image)
    sprite:close()
    sprite = nil
  end)
  if sprite ~= nil then pcall(function() sprite:close() end) end
  if previous.sprite ~= nil and previous.sprite.isValid then
    pcall(function() app.activeSprite = previous.sprite end)
    pcall(function() app.activeLayer = previous.layer end)
    pcall(function() app.activeFrame = previous.frame end)
  end
  return ok
end

local function observes_sprite_flatten()
  local sprite = nil
  local ok = pcall(function()
    sprite = Sprite(2, 2, ColorMode.RGB)
    sprite:newLayer()
    assert(#sprite.layers == 2)
    sprite:flatten()
    assert(#sprite.layers == 1)
    sprite:close()
    sprite = nil
  end)
  if sprite ~= nil then pcall(function() sprite:close() end) end
  return ok
end

local function observes_sprite_resize()
  local sprite = nil
  local ok = pcall(function()
    sprite = Sprite(2, 2, ColorMode.RGB)
    sprite:resize(4, 4)
    assert(sprite.width == 4 and sprite.height == 4)
    sprite:close()
    sprite = nil
  end)
  if sprite ~= nil then pcall(function() sprite:close() end) end
  return ok
end

local function observes_image_resize()
  if image_resize_transform == nil then return false end
  local sprite = nil
  local previous = { sprite = app.activeSprite, layer = app.activeLayer, frame = app.activeFrame }
  local ok = pcall(function()
    sprite = Sprite(2, 2, ColorMode.RGB)
    local target = sprite.layers[1]:cel(1)
    local source = Image(target.image)
    source:putPixel(0, 0, app.pixelColor.rgba(255, 0, 0, 255))
    local resized = image_resize_transform.resize(source, sprite, 4, 4, "nearest-neighbor")
    target.image = resized
    assert(target.image.width == 4 and target.image.height == 4)
    assert(target.image:getPixel(1, 1) == app.pixelColor.rgba(255, 0, 0, 255))
    sprite:close()
    sprite = nil
    sprite = Sprite(2, 2, ColorMode.INDEXED)
    local palette = Palette(4)
    palette:setColor(0, Color { r = 0, g = 0, b = 0, a = 0 })
    palette:setColor(1, Color { r = 255, g = 0, b = 0, a = 255 })
    palette:setColor(2, Color { r = 0, g = 0, b = 255, a = 255 })
    palette:setColor(3, Color { r = 127, g = 0, b = 127, a = 255 })
    app.activeSprite = sprite
    app.activeLayer = sprite.layers[1]
    app.activeFrame = sprite.frames[1]
    sprite:setPalette(palette)
    local indexed = sprite.layers[1]:cel(1)
    indexed.image:putPixel(0, 0, 1)
    indexed.image:putPixel(1, 0, 2)
    indexed.image:putPixel(0, 1, 1)
    indexed.image:putPixel(1, 1, 2)
    local copy, basis = image_resize_transform.resize(indexed.image, sprite, 3, 3, "bilinear", 1)
    assert(copy:getPixel(1, 1) == 3)
    assert(basis.palette_frame_number == 1 and basis.palette_size == 4)
    sprite:close()
    sprite = nil
  end)
  if sprite ~= nil then pcall(function() sprite:close() end) end
  if previous.sprite ~= nil and previous.sprite.isValid then
    pcall(function() app.activeSprite = previous.sprite end)
    pcall(function() app.activeLayer = previous.layer end)
    pcall(function() app.activeFrame = previous.frame end)
  end
  return ok
end

local function observes_sprite_crop()
  local sprite = nil
  local previous = app.activeSprite
  local ok = pcall(function()
    sprite = Sprite(3, 3, ColorMode.RGB)
    app.activeSprite = sprite
    app.command.CanvasSize {
      bounds = Rectangle(1, 1, 2, 2),
      trimOutside = true,
      ui = false,
    }
    assert(sprite.width == 2 and sprite.height == 2)
    sprite:close()
    sprite = nil
  end)
  if sprite ~= nil then pcall(function() sprite:close() end) end
  if previous ~= nil and previous.isValid then pcall(function() app.activeSprite = previous end) end
  return ok
end

local function observes_tag_authoring()
  local sprite = nil
  local previous = { sprite = app.activeSprite, layer = app.activeLayer, frame = app.activeFrame }
  local ok = pcall(function()
    sprite = Sprite(2, 2, ColorMode.RGB)
    sprite:newEmptyFrame(2)
    local tag = sprite:newTag(1, 2)
    tag.name = "probe"
    tag.aniDir = AniDir.PING_PONG_REVERSE
    tag.repeats = 0
    tag.toFrame = 1
    assert(#sprite.tags == 1 and tag.toFrame.frameNumber == 1)
    assert(tag.aniDir == AniDir.PING_PONG_REVERSE and tag.repeats == 0)
    sprite:deleteTag(tag)
    assert(#sprite.tags == 0)
    sprite:close()
    sprite = nil
  end)
  if sprite ~= nil then pcall(function() sprite:close() end) end
  if previous.sprite ~= nil and previous.sprite.isValid then
    pcall(function() app.activeSprite = previous.sprite end)
    pcall(function() app.activeLayer = previous.layer end)
    pcall(function() app.activeFrame = previous.frame end)
  end
  return ok
end

local function observes_image_flip()
  if image_orientation_transform == nil then return false end
  return pcall(function()
    local image = Image(3, 2, ColorMode.INDEXED)
    image:putPixel(0, 0, 7)
    image_orientation_transform.flip(image, "horizontal")
    assert(image:getPixel(2, 0) == 7 and image:getPixel(0, 0) == 0)
    image_orientation_transform.flip(image, "vertical")
    assert(image:getPixel(2, 1) == 7 and image:getPixel(2, 0) == 0)
  end)
end

local function observes_image_rotate()
  if image_orientation_transform == nil then return false end
  return pcall(function()
    local source = Image(3, 2, ColorMode.INDEXED)
    source:putPixel(2, 0, 9)
    local rotated = image_orientation_transform.rotate(source, 90)
    assert(rotated.width == 2 and rotated.height == 3 and rotated:getPixel(1, 2) == 9)
    assert(source:getPixel(2, 0) == 9)
  end)
end

function module.observe()
  local capabilities = { "aseprite_runtime_introspection" }
  local supports_inspection = observes_sprite_inspection()
  if supports_inspection and observes_sprite_creation() then
    capabilities[#capabilities + 1] = "aseprite_sprite_create"
  end
  if supports_inspection then capabilities[#capabilities + 1] = "aseprite_sprite_inspection" end
  if observes_sprite_flatten() then capabilities[#capabilities + 1] = "aseprite_sprite_flatten" end
  if observes_sprite_resize() then capabilities[#capabilities + 1] = "aseprite_sprite_resize" end
  if observes_image_resize() then capabilities[#capabilities + 1] = "aseprite_image_resize" end
  if observes_image_flip() then capabilities[#capabilities + 1] = "aseprite_image_flip" end
  if observes_image_rotate() then capabilities[#capabilities + 1] = "aseprite_image_rotate" end
  if observes_sprite_crop() then capabilities[#capabilities + 1] = "aseprite_sprite_crop" end
  if observes_layer_hierarchy() then
    capabilities[#capabilities + 1] = "aseprite_layer_hierarchy"
  end
  if observes_layer_mutation() then capabilities[#capabilities + 1] = "aseprite_layer_mutation" end
  if observes_layer_merge() then capabilities[#capabilities + 1] = "aseprite_layer_merge" end
  if observes_background_conversion() then
    capabilities[#capabilities + 1] = "aseprite_background_conversion"
  end
  if observes_paint_apply() then capabilities[#capabilities + 1] = "aseprite_paint_apply" end
  if observes_frame_authoring() then
    capabilities[#capabilities + 1] = "aseprite_frame_authoring"
  end
  if observes_frame_editing() then capabilities[#capabilities + 1] = "aseprite_frame_editing" end
  if observes_cel_lifecycle() then capabilities[#capabilities + 1] = "aseprite_cel_lifecycle" end
  if observes_cel_relationships() then
    capabilities[#capabilities + 1] = "aseprite_cel_relationships"
  end
  if observes_tag_authoring() then capabilities[#capabilities + 1] = "aseprite_tag_authoring" end
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
