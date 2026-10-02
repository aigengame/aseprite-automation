-- Shared runtime capability observations used by the probe and Plan.
local module = {}
local inspection = dofile(app.params.inspection)
local creation = dofile(app.params.creation)
local layer_select = app.params.layer_select and dofile(app.params.layer_select) or nil
local exporter = app.params.export_image_support and dofile(app.params.export_image_support) or nil
local paint = dofile(app.params.paint)
local paint_native = app.params.native_paint and dofile(app.params.native_paint) or nil
local digest = dofile(app.params.digest)
local frame = app.params.frame and dofile(app.params.frame) or nil
local cel_support = app.params.cel and dofile(app.params.cel) or nil
local image_resize_transform = app.params.image_resize_transform
    and dofile(app.params.image_resize_transform)
  or nil
local image_snapshot = app.params.image_snapshot and dofile(app.params.image_snapshot) or nil
local layer_composition = app.params.layer_composition and dofile(app.params.layer_composition)
  or nil
local raster_color = dofile(app.params.raster_color)
local selections = app.params.selection_support and dofile(app.params.selection_support) or nil
local image_orientation_transform = app.params.image_orientation_transform
    and dofile(app.params.image_orientation_transform)
  or nil

local function observes_palette_files()
  local path = app.params.capability_sprite .. ".gpl"
  local ok = pcall(function()
    local file = assert(io.open(path, "wb"))
    file:write(
      "GIMP Palette\nChannels: RGBA\n#\n11 22 33 0 zero\n44 55 66 128 partial\n"
        .. "44 55 66 128 duplicate\n77 88 99 255 opaque\n"
    )
    file:close()
    local palette = Palette { fromFile = path }
    assert(#palette == 4 and palette:getColor(1).alpha == 128)
    assert(palette:getColor(1).rgbaPixel == palette:getColor(2).rgbaPixel)
    for _, target in ipairs({ path, path .. ".png" }) do
      palette:saveAs(target)
      local reopened = Palette { fromFile = target }
      assert(#reopened == #palette)
      for index = 0, 3 do
        assert(reopened:getColor(index).rgbaPixel == palette:getColor(index).rgbaPixel)
      end
    end
  end)
  os.remove(path)
  os.remove(path .. ".png")
  return ok
end

local function observes_palette_quantization()
  if not app.params.palette_quantization then return false end
  local quantization = dofile(app.params.palette_quantization)
  local previous = { sprite = app.activeSprite, layer = app.activeLayer, frame = app.activeFrame }
  local sprite
  local ok = pcall(function()
    sprite = Sprite(3, 1, ColorMode.RGB)
    sprite.cels[1].image:drawPixel(0, 0, app.pixelColor.rgba(255, 0, 0, 255))
    sprite.cels[1].image:drawPixel(1, 0, app.pixelColor.rgba(0, 255, 0, 128))
    for _, algorithm in ipairs({ "default", "rgb5a3", "octree" }) do
      local alpha = algorithm ~= "rgb5a3"
      local result = quantization.apply(sprite, {
        palette_frame_number = "1",
        max_colors = "8",
        with_alpha = alpha,
        rgb_map_algorithm = algorithm,
        new_layer_blending_method = algorithm ~= "default",
      }, {})
      assert(not result.rejection and result.quantization.actual_colors == 3)
      local has_partial = false
      for _, entry in ipairs(result.palette.entries) do
        has_partial = has_partial or (entry.color.alpha > 0 and entry.color.alpha < 255)
      end
      assert(has_partial == alpha)
    end
  end)
  if sprite ~= nil then pcall(function() sprite:close() end) end
  if previous.sprite ~= nil and previous.sprite.isValid then
    app.activeSprite, app.activeLayer, app.activeFrame =
      previous.sprite, previous.layer, previous.frame
  end
  return ok
end

local function observes_change_color_mode()
  if not app.params.color_mode then return false end
  local color_mode = dofile(app.params.color_mode)
  local persistence = dofile(app.params.persistence)
  local sprite = nil
  local previous = { sprite = app.activeSprite, layer = app.activeLayer, frame = app.activeFrame }
  local ok = pcall(function()
    sprite = Sprite(1, 1, ColorMode.RGB)
    sprite.cels[1].image:drawPixel(0, 0, app.pixelColor.rgba(255, 0, 0, 255))
    local result = color_mode.change(sprite, {
      source_color_mode = "rgb",
      target = { color_mode = "grayscale", to_gray = "luma" },
    })
    assert(result.changed and result.after.images[1].bytes_per_pixel == 2)
    result = color_mode.change(sprite, {
      source_color_mode = "grayscale",
      target = {
        color_mode = "indexed",
        rgb_map_algorithm = "default",
        color_best_fit_criteria = "default",
      },
    })
    assert(result.changed and result.after.images[1].bytes_per_pixel == 1)
    result =
      color_mode.change(sprite, { source_color_mode = "indexed", target = { color_mode = "rgb" } })
    assert(result.changed and result.after.images[1].bytes_per_pixel == 4)
    result = color_mode.change(sprite, {
      source_color_mode = "rgb",
      target = {
        color_mode = "indexed",
        rgb_map_algorithm = "octree",
        color_best_fit_criteria = "rgb",
        dithering = { algorithm = "ordered" },
      },
    })
    assert(result.changed and result.dithering.matrix.identity == "bayer8x8")
    sprite = persistence.save_verified(sprite, app.params.capability_sprite, {}, "Color Mode probe")
    persistence.assert_equal(result.after, color_mode.observe(sprite), "Color Mode probe")
  end)
  if sprite ~= nil then pcall(function() sprite:close() end) end
  os.remove(app.params.capability_sprite)
  if previous.sprite and previous.sprite.isValid then
    pcall(function() app.activeSprite = previous.sprite end)
    pcall(function() app.activeLayer = previous.layer end)
    pcall(function() app.activeFrame = previous.frame end)
  end
  return ok
end

local function observes_color_profile(operation)
  if app.params.color_profile == nil or app.params.profile_linear_srgb == nil then return false end
  local profiles = dofile(app.params.color_profile)
  local sprite = nil
  local path = app.params.capability_sprite
  local previous = { sprite = app.activeSprite, layer = app.activeLayer, frame = app.activeFrame }
  local ok = pcall(function()
    sprite = Sprite(1, 1, ColorMode.RGB)
    sprite:assignColorSpace(ColorSpace { sRGB = true })
    sprite.cels[1].image:drawPixel(0, 0, app.pixelColor.rgba(48, 96, 144, 255))
    sprite.palettes[1]:resize(2)
    sprite.palettes[1]:setColor(0, Color { r = 32, g = 64, b = 96, a = 255 })
    sprite.palettes[1]:setColor(1, Color { r = 48, g = 96, b = 144, a = 255 })
    local function icc_input(icc_path)
      local file = assert(io.open(icc_path, "rb"))
      local bytes = assert(file:read("a"))
      file:close()
      return {
        profile = { kind = "icc", icc_file = icc_path },
        icc_bytes = bytes:gsub(".", function(value) return string.format("%02x", value:byte()) end),
        icc_file = { path = icc_path, byte_size = #bytes, sha256 = string.rep("0", 64) },
      }
    end
    local profile_state = {}
    local function verify(input_profile)
      local result = profiles.apply_live(sprite, operation, input_profile, {}, profile_state)
      assert(result.rejection == nil and result.matches_requested_profile)
      local live = profiles.snapshot(sprite, {})
      assert(sprite:saveAs(path))
      sprite:close()
      sprite = assert(app.open(path))
      profile_state = profiles.restore_file_profile(sprite, path)
      profiles.verify_persisted(live, sprite, inspection.saved_layer_uuids(sprite, path))
      return result
    end
    local changed = verify(icc_input(app.params.profile_linear_srgb))
    assert(changed.images[1].changed == (operation == "convert"))
    assert(changed.palettes[1].changed == (operation == "convert"))
    local restored = verify { profile = { kind = "srgb" } }
    assert(restored.images[1].changed == (operation == "convert"))
    assert(restored.palettes[1].changed == (operation == "convert"))
    if operation == "assign" then
      verify { profile = { kind = "none" } }
    else
      -- This separate direction is required by Asset Preparation (#103).
      local assigned = profiles.apply_live(
        sprite,
        "assign",
        icc_input(app.params.profile_display_p3),
        {},
        profile_state
      )
      assert(assigned.rejection == nil)
      local sample = app.pixelColor.rgba(180, 70, 30, 127)
      sprite.cels[1].image:drawPixel(0, 0, sample)
      sprite.palettes[1]:setColor(1, Color { r = 180, g = 70, b = 30, a = 127 })
      verify { profile = { kind = "srgb" } }
      local expected = app.pixelColor.rgba(195, 60, 2, 127)
      assert(sprite.cels[1].image:getPixel(0, 0) == expected)
      assert(sprite.palettes[1]:getColor(1).rgbaPixel == expected)
    end
  end)
  if sprite ~= nil then pcall(function() sprite:close() end) end
  pcall(function() os.remove(path) end)
  if previous.sprite ~= nil and previous.sprite.isValid then
    pcall(function() app.activeSprite = previous.sprite end)
    pcall(function() app.activeLayer = previous.layer end)
    pcall(function() app.activeFrame = previous.frame end)
  end
  return ok
end

local function observes_palette_entries()
  if app.params.palette == nil or app.params.persistence == nil then return false end
  local palettes = dofile(app.params.palette)
  local persistence = dofile(app.params.persistence)
  local sprite = nil
  local previous = { sprite = app.activeSprite, layer = app.activeLayer, frame = app.activeFrame }
  local path = assert(app.params.capability_sprite)
  local ok = pcall(function()
    for _, mode in ipairs { ColorMode.RGB, ColorMode.GRAY, ColorMode.INDEXED } do
      sprite = Sprite(1, 1, mode)
      sprite:newEmptyFrame()
      local before_count = #sprite.palettes
      local live = palettes.set(sprite, {
        palette_frame_number = 1,
        entries = { { index = 1, color = { red = 12, green = 34, blue = 56, alpha = 77 } } },
      }, {})
      assert(live.rejection == nil and #sprite.palettes == before_count)
      local got = palettes.get(sprite, 2)
      assert(got.palette.palette_frame_number == 1)
      assert(got.palette.entries[2].color.alpha == 77)
      sprite = persistence.save_verified(sprite, path, {}, "Palette entry probe")
      persistence.assert_equal(live, palettes.list(sprite), "Palette entry probe")
      sprite:close()
      sprite = nil
    end
  end)
  if sprite ~= nil then pcall(function() sprite:close() end) end
  pcall(function() os.remove(path) end)
  if previous.sprite ~= nil and previous.sprite.isValid then
    pcall(function() app.activeSprite = previous.sprite end)
    pcall(function() app.activeLayer = previous.layer end)
    pcall(function() app.activeFrame = previous.frame end)
  end
  return ok
end

local function observes_palette_transform(operation)
  if app.params.palette_transform == nil then return false end
  local transform = dofile(app.params.palette_transform)
  local palettes = dofile(app.params.palette)
  local persistence = dofile(app.params.persistence)
  local sprite = nil
  local previous = { sprite = app.activeSprite, layer = app.activeLayer, frame = app.activeFrame }
  local path = assert(app.params.capability_sprite)
  local ok = pcall(function()
    sprite = Sprite(1, 1, ColorMode.INDEXED)
    sprite.palettes[1]:resize(2)
    local live
    if operation == "resize" then
      live = transform.resize(sprite, {
        palette_frame_number = "1",
        size = "3",
        entries = { { index = "2", color = { red = 12, green = 34, blue = 56, alpha = 77 } } },
      }, {})
      assert(live.rejection == nil and #sprite.palettes[1] == 3)
    else
      sprite.cels[1].image:putPixel(0, 0, 1)
      live = transform[operation](sprite, {
        scope = "sprite",
        mapping = { { old_index = "0", new_index = "1" }, { old_index = "1", new_index = "0" } },
      }, {})
      assert(
        live.rejection == nil
          and sprite.cels[1].image:getPixel(0, 0) == 0
          and sprite.transparentColor == 1
      )
    end
    sprite = persistence.save_verified(sprite, path, {}, "Palette resize probe")
    persistence.assert_equal(
      { frame_count = live.frame_count, palette_changes = live.palette_changes },
      palettes.list(sprite),
      "Palette transform probe"
    )
    sprite:close()
    sprite = nil
  end)
  if sprite ~= nil then pcall(function() sprite:close() end) end
  pcall(function() os.remove(path) end)
  if previous.sprite ~= nil and previous.sprite.isValid then
    pcall(function() app.activeSprite = previous.sprite end)
    pcall(function() app.activeLayer = previous.layer end)
    pcall(function() app.activeFrame = previous.frame end)
  end
  return ok
end

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

local function observes_image_canvas_transform()
  if app.params.image_canvas_transform == nil then return false end
  return pcall(function()
    local transform = dofile(app.params.image_canvas_transform)
    local source = Image(2, 2, ColorMode.RGB)
    local pixel = app.pixelColor.rgba(10, 20, 30, 0)
    source:putPixel(1, 0, pixel)
    local cropped = transform.crop(source, { x = 1, y = 0, width = 1, height = 2 })
    assert(cropped.width == 1 and cropped.height == 2)
    assert(cropped:getPixel(0, 0) == pixel and source:getPixel(1, 0) == pixel)
    local shifted = transform.canvas_resize(
      source,
      3,
      3,
      { x = -1, y = 1 },
      { kind = "rgba", red = 0, green = 255, blue = 0, alpha = 255 }
    )
    assert(shifted:getPixel(0, 1) == pixel)
    assert(shifted:getPixel(2, 2) == app.pixelColor.rgba(0, 255, 0, 255))
    local gray = transform.canvas_resize(
      Image(1, 1, ColorMode.GRAY),
      2,
      1,
      { x = 2, y = 0 },
      { kind = "grayscale", gray = 73, alpha = 0 }
    )
    assert(gray:getPixel(0, 0) == app.pixelColor.graya(73, 0))
    local indexed = Image(
      ImageSpec { width = 1, height = 1, colorMode = ColorMode.INDEXED, transparentColor = 2 }
    )
    local filled = transform.canvas_resize(
      indexed,
      2,
      1,
      { x = -1, y = 0 },
      json.decode('{"kind":"palette-index","index":2}')
    )
    assert(filled:getPixel(0, 0) == 2 and filled.spec.transparentColor == 2)
  end)
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

local function observes_image_snapshot()
  if image_snapshot == nil or layer_composition == nil then return false end
  local sprite = nil
  local previous = { sprite = app.activeSprite, layer = app.activeLayer, frame = app.activeFrame }
  local ok = pcall(function()
    for _, mode in ipairs({ ColorMode.RGB, ColorMode.GRAY, ColorMode.INDEXED }) do
      sprite = Sprite(2, 1, mode)
      local image = sprite.layers[1]:cel(1).image
      local value = mode == ColorMode.RGB and app.pixelColor.rgba(1, 2, 3, 0)
        or mode == ColorMode.GRAY and app.pixelColor.graya(7, 0)
        or raster_color.native_color(
          json.decode('{"kind":"palette-index","index":3}'),
          "indexed",
          false
        )
      image:putPixel(0, 0, value)
      assert(image:getPixel(0, 0) == value)
      local result = image_snapshot.read(image, { x = 0, y = 0, width = 1, height = 1 })
      local color = result.rows[1][1].color
      assert(color.red == 1 or color.gray == 7 or color.index == 3)
      if mode == ColorMode.INDEXED then
        sprite.transparentColor = 2
        sprite.palettes[1]:setColor(3, Color { r = 12, g = 34, b = 56, a = 255 })
        image:putPixel(1, 0, 2)
        local rendered = assert(
          layer_composition.render(
            sprite,
            1,
            { mode = "visible" },
            { x = 0, y = 0, width = 2, height = 1 },
            layer_select,
            {},
            "rgb"
          )
        )
        assert(rendered:getPixel(0, 0) == app.pixelColor.rgba(12, 34, 56, 255))
        assert(rendered:getPixel(1, 0) == 0)
        assert(image:getPixel(0, 0) == 3 and image:getPixel(1, 0) == 2)
      end
      sprite:close()
      sprite = nil
    end
    sprite = Sprite(2, 2, ColorMode.RGB)
    sprite.layers[1]:cel(1).image:putPixel(1, 1, app.pixelColor.rgba(255, 0, 0, 255))
    sprite.layers[1].isVisible = false
    local image = assert(
      layer_composition.render(
        sprite,
        1,
        { mode = "include", layers = { { layer_path = { 1 } } } },
        { x = 1, y = 1, width = 1, height = 1 },
        layer_select,
        {},
        "preserve"
      )
    )
    assert(image:getPixel(0, 0) == app.pixelColor.rgba(255, 0, 0, 255))
    assert(not sprite.layers[1].isVisible)
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

local function observes_native_paint(tool, algorithm, tiled)
  if paint_native == nil then return false end
  local source = app.fs.joinPath(app.params.workspace, "native-" .. tool .. ".aseprite")
  local output = app.fs.joinPath(app.params.workspace, "native-" .. tool .. "-painted.aseprite")
  local previous = { sprite = app.activeSprite, layer = app.activeLayer, frame = app.activeFrame }
  local sprite
  local ok = pcall(function()
    sprite = Sprite(8, 8, ColorMode.RGB)
    if tool == "eraser" then sprite.cels[1].image:clear(app.pixelColor.rgba(255, 0, 0, 255)) end
    if tool == "blur" then
      local image = sprite.layers[1]:cel(1).image
      image:clear(app.pixelColor.rgba(0, 0, 255, 255))
      image:putPixel(0, 0, app.pixelColor.rgba(255, 0, 0, 255))
    end
    assert(sprite:saveAs(source))
    sprite:close()
    sprite = nil
    local result = paint_native.execute({
      source_sprite_file = source,
      staged_sprite_file = output,
      target = { layer = { layer_path = { 1 } }, frame_number = 1 },
      coordinate_space = "image-pixel",
      brush = { kind = "circle", size = 1 },
      color = tool ~= "blur" and { kind = "rgba", red = 255, green = 0, blue = 0, alpha = 255 }
        or nil,
      ink = tool ~= "blur" and "simple" or nil,
      opacity = (tool == "eraser" or tool == "blur") and 255 or 0,
      clipping = "reject",
      bounds = { x = 2, y = 2, width = 4, height = 3 },
      style = tool:match("^filled_") and "filled" or "outline",
      ["from"] = { x = 2, y = 2 },
      to = { x = 5, y = 2 },
      points = tool == "blur" and { { x = 0, y = 0 } }
        or tool == "contour" and {
          { x = 1, y = 1 },
          { x = 2, y = 1 },
          { x = 2, y = 2 },
          { x = 3, y = 2 },
          { x = 3, y = 3 },
          { x = 4, y = 3 },
        }
        or algorithm == "pixel-perfect" and { { x = 2, y = 2 }, { x = 3, y = 2 }, { x = 3, y = 3 } }
        or { { x = 2, y = 2 }, { x = 5, y = 2 } },
      freehand_algorithm = algorithm or "regular",
      tiled_mode = tiled,
      behavior = { kind = "erase" },
      seed = { x = 1, y = 1 },
      tolerance = 0,
      contiguous = true,
      connectivity = "four-connected",
      refer_to = "active-layer",
      stop_at_grid = false,
    }, tool)
    assert(result.persisted_reopen_verified and result.pixels_changed > 0)
    if tool == "line" then assert(result.pixels_changed == 4) end
    if tool == "blur" then
      assert(result.requested_opacity == 255 and result.effective_opacity == 255)
      sprite = assert(app.open(output))
      local pixel = sprite.layers[1]:cel(1).image:getPixel(0, 0)
      -- Independent 1.3.18.5 native oracle: one red corner on opaque blue.
      -- These include native source-area expansion and tiled edge sampling.
      local expected = ({
        none = app.pixelColor.rgba(113, 0, 141, 255),
        x = app.pixelColor.rgba(85, 0, 170, 170),
        y = app.pixelColor.rgba(85, 0, 170, 170),
        both = app.pixelColor.rgba(63, 0, 191, 113),
      })[tiled]
      assert(pixel == expected)
    else
      assert(
        result.requested_opacity == (tool == "eraser" and 255 or 0)
          and result.effective_opacity == 255
      )
      if tool == "contour" then
        assert(result.pixels_changed == (algorithm == "pixel-perfect" and 5 or 6))
      elseif algorithm ~= nil then
        assert(result.pixels_changed == (algorithm == "regular" and 4 or 2))
      end
    end
  end)
  if sprite ~= nil then pcall(function() sprite:close() end) end
  os.remove(source)
  os.remove(output)
  if previous.sprite ~= nil and previous.sprite.isValid then
    app.activeSprite, app.activeLayer, app.activeFrame =
      previous.sprite, previous.layer, previous.frame
  end
  return ok
end

local function observes_manual_tilemap_filter()
  if app.params.filter_tiles == nil then return false end
  local tiles = dofile(app.params.filter_tiles)
  local persistence = dofile(app.params.persistence)
  local sprite
  local path = app.params.capability_sprite
  local ok = pcall(function()
    for _, branch in ipairs({ "rgb", "grayscale", "indexed", "rgb-palette-colors" }) do
      local mode = branch == "rgb-palette-colors" and "rgb" or branch
      local modes = { rgb = ColorMode.RGB, grayscale = ColorMode.GRAY, indexed = ColorMode.INDEXED }
      sprite = Sprite(1, 1, modes[mode])
      local ordinary = sprite.layers[1]
      local palette = sprite.palettes[1]
      palette:resize(3)
      palette:setColor(0, Color { r = 0, g = 0, b = 0, a = 0 })
      palette:setColor(1, Color { r = 80, g = 40, b = 20, a = 100 })
      palette:setColor(2, Color { r = 120, g = 40, b = 20, a = 101 })
      sprite.gridBounds = Rectangle(0, 0, 1, 1)
      assert(app.command.NewLayer { tilemap = true, ui = false })
      local layer = app.activeLayer
      local tile = sprite:newTile(layer.tileset)
      local original = mode == "indexed" and 1
        or (
          mode == "grayscale" and app.pixelColor.graya(80, 100)
          or app.pixelColor.rgba(80, 40, 20, 100)
        )
      tile.image:putPixel(0, 0, original)
      local map = Image(1, 1, ColorMode.TILEMAP)
      map:putPixel(0, 0, 1)
      sprite:newCel(layer, 1, map, Point(0, 0))
      sprite:deleteLayer(ordinary)
      app.activeCel = layer:cel(1)
      assert(app.site.tilesetMode == TilesetMode.MANUAL)
      app.range:clear()
      app.range.colors = branch == "rgb-palette-colors" and { 1 } or {}
      sprite.selection = Selection(Rectangle(0, 0, 1, 1))
      assert(app.command.BrightnessContrast {
        ui = false,
        brightness = 50,
        contrast = 0,
        channels = mode == "grayscale" and FilterChannels.GRAY or FilterChannels.RED,
      })
      local expected = mode == "indexed" and 2
        or (
          mode == "grayscale" and app.pixelColor.graya(120, 100)
          or app.pixelColor.rgba(120, 40, 20, 100)
        )
      assert(tile.image:getPixel(0, 0) == expected)
      assert(layer:cel(1).image:getPixel(0, 0) == 1 and #layer.tileset == 2)
      assert(palette:getColor(1).red == (branch == "rgb-palette-colors" and 120 or 80))
      local live = tiles.snapshot(sprite, mode)
      assert(sprite:saveAs(path))
      sprite:close()
      sprite = assert(app.open(path))
      persistence.assert_equal(live, tiles.snapshot(sprite, mode), "Manual Tilemap Filter probe")
      sprite:close()
      sprite = nil
    end
  end)
  if sprite ~= nil then pcall(function() sprite:close() end) end
  os.remove(path)
  return ok
end

function module.observe()
  local capabilities = { "aseprite_runtime_introspection" }
  if app.params.paint_composite ~= nil then
    local ok = pcall(function()
      local composite = dofile(app.params.paint_composite)
      local destination, source = Image(1, 1, ColorMode.RGB), Image(1, 1, ColorMode.RGB)
      source:putPixel(0, 0, app.pixelColor.rgba(240, 80, 20, 128))
      local result = composite.draw(destination, source, { x = 0, y = 0 }, 255, "normal")
      assert(result:getPixel(0, 0) == app.pixelColor.rgba(240, 80, 20, 128))
    end)
    if ok then capabilities[#capabilities + 1] = "aseprite_paint_composite" end
    local indexed_ok = pcall(function()
      local composite = dofile(app.params.paint_composite)
      local spec =
        ImageSpec { width = 2, height = 1, colorMode = ColorMode.INDEXED, transparentColor = 7 }
      local destination, source = Image(spec), Image(spec)
      destination:clear(1)
      source:putPixel(0, 0, 7)
      source:putPixel(1, 0, 8)
      local missing = composite.draw_indexed(destination, source, { x = 0, y = 0 }, Palette(8))
      local present = composite.draw_indexed(destination, source, { x = 0, y = 0 }, Palette(9))
      assert(missing:getPixel(1, 0) == 1)
      assert(present:getPixel(0, 0) == 1 and present:getPixel(1, 0) == 8)
      assert(destination:getPixel(0, 0) == 1 and destination:getPixel(1, 0) == 1)
    end)
    if indexed_ok then capabilities[#capabilities + 1] = "aseprite_paint_composite_indexed" end
  end
  if selections ~= nil then
    local ok = pcall(function()
      local bounds = { x = -2, y = 3, width = 4, height = 4 }
      local ellipse = selections.create { shape = { kind = "ellipse", bounds = bounds } }
      assert(ellipse.pixel_count == 12 and ellipse.bounds.x == -2)
      local dot = { kind = "all", rectangle = { x = -1, y = 4, width = 1, height = 1 } }
      local grown =
        selections.grow { selection = dot, canvas = bounds, radius = 1, shape = "circle" }
      assert(grown.pixel_count == 5)
      local shrunken = selections.shrink {
        selection = grown.selection,
        canvas = bounds,
        radius = 1,
        shape = "circle",
      }
      assert(shrunken.pixel_count == 1)
      local flipped = selections.transform {
        selection = grown.selection,
        canvas = bounds,
        transform = { kind = "flip", axis = "horizontal" },
      }
      assert(flipped.pixel_count == 5)
      local rotated = selections.transform {
        selection = grown.selection,
        canvas = bounds,
        transform = { kind = "rotate", angle = 90 },
      }
      assert(rotated.pixel_count == 5)
      local scaled = selections.transform {
        selection = dot,
        canvas = bounds,
        transform = { kind = "scale", width = 2, height = 2 },
      }
      assert(scaled.pixel_count == 4)
    end)
    if ok then capabilities[#capabilities + 1] = "aseprite_selection" end
  end
  local supports_inspection = observes_sprite_inspection()
  if app.params.brightness_contrast then
    local filter = dofile(app.params.brightness_contrast)
    local modes = { rgb = ColorMode.RGB, grayscale = ColorMode.GRAY, indexed = ColorMode.INDEXED }
    local supported = true
    for _, branch in ipairs({
      { mode = "rgb", kind = "pixels" },
      { mode = "grayscale", kind = "pixels" },
      { mode = "indexed", kind = "pixels" },
      { mode = "indexed", kind = "indexed-palette-entries" },
      { mode = "rgb", kind = "rgb-palette-colors" },
    }) do
      local sprite = Sprite(1, 1, modes[branch.mode])
      local ok = pcall(function()
        local palette = Palette(3)
        palette:setColor(0, Color { r = 0, g = 0, b = 0, a = 0 })
        palette:setColor(1, Color { r = 80, g = 40, b = 20, a = 100 })
        palette:setColor(2, Color { r = 120, g = 40, b = 20, a = 100 })
        sprite:setPalette(palette)
        local original = branch.mode == "indexed" and 1
          or (
            branch.mode == "grayscale" and app.pixelColor.graya(80, 100)
            or app.pixelColor.rgba(80, 40, 20, 100)
          )
        sprite.cels[1].image:drawPixel(0, 0, original)
        local application = {
          kind = branch.kind,
          channels = {
            kind = "components",
            names = { branch.mode == "grayscale" and "gray" or "red" },
          },
        }
        if branch.kind == "indexed-palette-entries" then
          application.entries = { kind = "selected", indexes = { 1 } }
        else
          application.cels_target = { kind = "all" }
        end
        if branch.kind == "pixels" then application.color_mode = branch.mode end
        if branch.kind == "rgb-palette-colors" then application.indexes = { 1 } end
        if branch.mode == "indexed" or branch.kind == "rgb-palette-colors" then
          application.palette_frame_number = 1
        end
        local result =
          filter.apply(sprite, { brightness = 50, contrast = 0, application = application })
        local expected = branch.kind == "indexed-palette-entries" and original
          or (
            branch.mode == "indexed" and 2
            or (
              branch.mode == "grayscale" and app.pixelColor.graya(120, 100)
              or app.pixelColor.rgba(120, 40, 20, 100)
            )
          )
        assert(result.changed and sprite.cels[1].image:getPixel(0, 0) == expected)
        assert(sprite.palettes[1]:getColor(1).red == (branch.kind == "pixels" and 80 or 120))
      end)
      sprite:close()
      supported = supported and ok
    end
    if supported then capabilities[#capabilities + 1] = "aseprite_filter_brightness_contrast" end
    if observes_manual_tilemap_filter() then
      capabilities[#capabilities + 1] = "aseprite_filter_brightness_contrast_tilemap_manual"
    end
  end
  if app.params.hue_saturation then
    local filter = dofile(app.params.hue_saturation)
    local supported = true
    -- Discriminating native observations: add and multiply must not collapse to
    -- the command's HSL fallback. Every delivered application uses this seam.
    for _, sample in ipairs {
      { mode = "hsl-multiply", rgb = { 134, 72, 10 } },
      { mode = "hsv-multiply", rgb = { 120, 60, 0 } },
      { mode = "hsl-add", rgb = { 218, 111, 4 } },
      { mode = "hsv-add", rgb = { 151, 76, 0 } },
    } do
      for _, branch in ipairs {
        { mode = "rgb", kind = "pixels" },
        { mode = "grayscale", kind = "pixels" },
        { mode = "indexed", kind = "pixels" },
        { mode = "indexed", kind = "indexed-palette-entries" },
        { mode = "rgb", kind = "rgb-palette-colors" },
      } do
        local modes =
          { rgb = ColorMode.RGB, grayscale = ColorMode.GRAY, indexed = ColorMode.INDEXED }
        local sprite = Sprite(1, 1, modes[branch.mode])
        local ok = pcall(function()
          local expected_rgb = app.pixelColor.rgba(sample.rgb[1], sample.rgb[2], sample.rgb[3], 128)
          local original_rgb = app.pixelColor.rgba(100, 60, 20, 128)
          local palette = Palette(3)
          palette:setColor(0, Color { r = 0, g = 0, b = 0, a = 0 })
          palette:setColor(1, Color { r = 100, g = 60, b = 20, a = 128 })
          palette:setColor(
            2,
            Color { r = sample.rgb[1], g = sample.rgb[2], b = sample.rgb[3], a = 128 }
          )
          sprite:setPalette(palette)
          local original = branch.mode == "indexed" and 1
            or (branch.mode == "grayscale" and app.pixelColor.graya(80, 128) or original_rgb)
          sprite.cels[1].image:drawPixel(0, 0, original)
          local application = {
            kind = branch.kind,
            channels = {
              kind = "components",
              names = branch.mode == "grayscale" and { "gray" } or { "red", "green", "blue" },
            },
          }
          if branch.kind == "indexed-palette-entries" then
            application.entries = { kind = "selected", indexes = { 1 } }
          else
            application.cels_target = { kind = "all" }
          end
          if branch.kind == "pixels" then application.color_mode = branch.mode end
          if branch.kind == "rgb-palette-colors" then application.indexes = { 1 } end
          if branch.mode == "indexed" or branch.kind == "rgb-palette-colors" then
            application.palette_frame_number = 1
          end
          local adjustment = { mode = sample.mode, hue = 0, saturation = 30 }
          if sample.mode:sub(1, 3) == "hsv" then
            adjustment.value = 20
          else
            adjustment.lightness = 20
          end
          if branch.mode == "grayscale" then adjustment = { mode = "grayscale", lightness = 20 } end
          local result =
            filter.apply(sprite, { application = application, adjustment = adjustment })
          local expected = branch.kind == "indexed-palette-entries" and original
            or (
              branch.mode == "indexed" and 2
              or (branch.mode == "grayscale" and app.pixelColor.graya(96, 128) or expected_rgb)
            )
          assert(result.changed and sprite.cels[1].image:getPixel(0, 0) == expected)
          assert(
            sprite.palettes[1]:getColor(1).rgbaPixel
              == (branch.kind == "pixels" and original_rgb or expected_rgb)
          )
        end)
        sprite:close()
        supported = supported and ok
      end
    end
    if supported then capabilities[#capabilities + 1] = "aseprite_filter_hue_saturation" end
  end
  if app.params.despeckle and dofile(app.params.despeckle).observe_support() then
    capabilities[#capabilities + 1] = "aseprite_filter_despeckle"
  end
  if observes_change_color_mode() then
    capabilities[#capabilities + 1] = "aseprite_change_color_mode"
  end
  if observes_color_profile("assign") then
    capabilities[#capabilities + 1] = "aseprite_assign_color_profile"
  end
  if observes_color_profile("convert") then
    capabilities[#capabilities + 1] = "aseprite_convert_color_profile"
  end
  if observes_palette_entries() then
    capabilities[#capabilities + 1] = "aseprite_palette_entries"
  end
  if observes_palette_files() then capabilities[#capabilities + 1] = "aseprite_palette_files" end
  if observes_palette_quantization() then
    capabilities[#capabilities + 1] = "aseprite_palette_quantization"
  end
  if observes_palette_transform("resize") then
    capabilities[#capabilities + 1] = "aseprite_palette_resize"
  end
  if observes_palette_transform("remap") then
    capabilities[#capabilities + 1] = "aseprite_palette_remap"
  end
  if observes_palette_transform("reorder") then
    capabilities[#capabilities + 1] = "aseprite_palette_reorder"
  end
  if supports_inspection and observes_sprite_creation() then
    capabilities[#capabilities + 1] = "aseprite_sprite_create"
  end
  if supports_inspection then capabilities[#capabilities + 1] = "aseprite_sprite_inspection" end
  if observes_sprite_flatten() then capabilities[#capabilities + 1] = "aseprite_sprite_flatten" end
  if observes_sprite_resize() then capabilities[#capabilities + 1] = "aseprite_sprite_resize" end
  if observes_image_canvas_transform() then
    capabilities[#capabilities + 1] = "aseprite_image_canvas_transform"
  end
  if observes_image_resize() then capabilities[#capabilities + 1] = "aseprite_image_resize" end
  if observes_image_snapshot() then capabilities[#capabilities + 1] = "aseprite_image_snapshot" end
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
  if observes_native_paint("paint_bucket") then
    capabilities[#capabilities + 1] = "aseprite_paint_fill"
  end
  if observes_native_paint("line") then capabilities[#capabilities + 1] = "aseprite_paint_line" end
  for _, tool in ipairs { "pencil", "eraser" } do
    local observed = {}
    for _, algorithm in ipairs { "regular", "pixel-perfect", "dots" } do
      if observes_native_paint(tool, algorithm) then
        observed[#observed + 1] = "aseprite_paint_" .. tool .. "_" .. algorithm:gsub("-", "_")
      end
    end
    if #observed > 0 then
      capabilities[#capabilities + 1] = "aseprite_paint_" .. tool
      for _, capability in ipairs(observed) do
        capabilities[#capabilities + 1] = capability
      end
    end
  end
  if observes_native_paint("rectangle") and observes_native_paint("filled_rectangle") then
    capabilities[#capabilities + 1] = "aseprite_paint_rectangle"
  end
  if observes_native_paint("ellipse") and observes_native_paint("filled_ellipse") then
    capabilities[#capabilities + 1] = "aseprite_paint_ellipse"
  end
  if
    observes_native_paint("contour", "regular")
    and observes_native_paint("contour", "pixel-perfect")
  then
    capabilities[#capabilities + 1] = "aseprite_paint_contour"
  end
  if
    observes_native_paint("blur", "regular", "none")
    and observes_native_paint("blur", "pixel-perfect", "x")
    and observes_native_paint("blur", "regular", "y")
    and observes_native_paint("blur", "pixel-perfect", "both")
  then
    capabilities[#capabilities + 1] = "aseprite_paint_blur"
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
