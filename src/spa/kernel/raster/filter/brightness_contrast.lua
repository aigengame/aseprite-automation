-- Aseprite owns percentage conversion, channel math, quantization, and clamping.
local module = {}
local json_null = json.decode("null")
local support = dofile(app.params.filter_support)
local digest = dofile(app.params.digest)
local palette = dofile(app.params.palette)
local effective = dofile(app.params.effective_palette)
local persistence = dofile(app.params.persistence)
local tiles = dofile(app.params.filter_tiles)

function module.apply(sprite, payload, uuids)
  local application = payload.application
  local palette_only = application.kind == "indexed-palette-entries"
  local rgb_palette = application.kind == "rgb-palette-colors"
  local mode = palette_only and "indexed" or (rgb_palette and "rgb" or application.color_mode)
  local modes = { rgb = ColorMode.RGB, grayscale = ColorMode.GRAY, indexed = ColorMode.INDEXED }
  if sprite.colorMode ~= modes[mode] then
    return support.reject("Source Color Mode differs from application", true)
  end
  local targets, rejection
  if palette_only then
    targets = {
      images = {},
      requested_intersections = {},
      existing_target_cels = {},
      excluded_layers = {},
      affected_cels = {},
    }
  else
    targets, rejection = support.targets(sprite, application.cels_target, uuids, mode)
    if rejection then return rejection end
  end
  local flags, channels = support.channels(application.channels)
  local anchor = targets.images[1] and targets.images[1].cel
  local basis, picks = json_null, {}
  if application.palette_frame_number then
    local frame = application.palette_frame_number
    if frame > #sprite.frames then
      return support.reject("Palette Frame is outside the timeline")
    end
    local resolved, change = effective.resolve(sprite, frame)
    if (palette_only or rgb_palette) and frame ~= change then
      return support.reject("Palette mutation requires an exact Palette Change")
    end
    basis = { frame_number = frame, palette_frame_number = change, palette_size = #resolved }
    if palette_only or rgb_palette then
      if palette_only and application.entries.kind == "all" then
        for index = 0, #resolved - 1 do
          picks[#picks + 1] = index
        end
      else
        for _, index in ipairs(rgb_palette and application.indexes or application.entries.indexes) do
          if index >= #resolved then
            return support.reject("Palette Index is outside the Palette")
          end
          picks[#picks + 1] = math.tointeger(index)
        end
      end
    end
    anchor = nil
    for _, cel in ipairs(sprite.cels) do
      if cel.frame.frameNumber == frame and not cel.layer.isReference then
        anchor = cel
        break
      end
    end
    if not anchor then
      return support.reject("Palette basis Frame has no native-safe image anchor", true)
    end
  end
  local palette_before = palette.list(sprite)
  table.sort(picks)
  local before = palette_only and support.snapshot(sprite, uuids, true)
  return support.with_state(sprite, function()
    app.activeSprite = sprite
    local tile_anchor = tiles.anchor(targets)
    if tile_anchor then
      app.activeCel = tile_anchor
      local refused = tiles.admit(application, payload.tilemap_manual_filter_available)
      if refused then return support.reject(refused, true) end
    end
    app.activeCel = anchor
    -- Verify the command's actual Site too, including an explicit Palette anchor.
    if tile_anchor then
      local refused = tiles.admit(application, payload.tilemap_manual_filter_available)
      if refused then return support.reject(refused, true) end
    end
    app.range:clear()
    if not palette_only then
      app.range.layers = targets.layers
      app.range.frames = targets.frames
    end
    app.range.colors = picks
    local effective_selection = json_null
    if palette_only then
      sprite.selection = Selection()
    else
      local mask
      mask, effective_selection = support.pixel_selection(sprite, application.selection)
      sprite.selection = mask
    end
    local result
    local tile_before = tiles.snapshot(sprite, mode)
    app.transaction("Brightness/Contrast", function()
      local filtering = payload.brightness ~= 0 or payload.contrast ~= 0
      if filtering then
        assert(
          app.command.BrightnessContrast {
            ui = false,
            channels = flags,
            brightness = payload.brightness,
            contrast = payload.contrast,
          },
          "Native Brightness/Contrast failed"
        )
      end
      local images, processed, changed = {}, {}, false
      for number, image in ipairs(targets.images) do
        if filtering then processed[#processed + 1] = number end
        local after = digest.image_content(image.cel.image, image.mode)
        local differs = image.before.value ~= after.value
        changed = changed or differs
        images[#images + 1] = {
          image_number = number,
          image_kind = image.image_kind,
          before_content_digest = image.before,
          after_content_digest = after,
          changed = differs,
        }
      end
      local palette_after = palette.list(sprite)
      local changed_tiles = tiles.changes(tile_before, tiles.snapshot(sprite, mode), targets)
      changed = changed or #changed_tiles > 0
      if palette_only then
        persistence.assert_equal(
          before,
          support.snapshot(sprite, uuids, true),
          "Palette-only Filter Images"
        )
        changed = not persistence.equal(palette_before, palette_after)
      elseif not rgb_palette then
        persistence.assert_equal(palette_before, palette_after, "Pixel Filter Palette")
      end
      changed = changed or not persistence.equal(palette_before, palette_after)
      result = {
        brightness = payload.brightness,
        contrast = payload.contrast,
        application = application.kind,
        cels_target_kind = application.cels_target and application.cels_target.kind or json_null,
        selection = effective_selection,
        palette_indexes = picks,
        processed_image_numbers = processed,
        color_mode = mode,
        palette_basis = basis,
        palette_before = palette_before,
        palette_after = palette_after,
        channels = channels,
        images = images,
        requested_tileset_mode = application.tileset_mode or json_null,
        observed_tileset_mode = tile_anchor and "manual" or json_null,
        changed_tiles = changed_tiles,
        changed = changed,
        requested_intersections = targets.requested_intersections,
        existing_target_cels = targets.existing_target_cels,
        excluded_layers = targets.excluded_layers,
        affected_cels = targets.affected_cels,
      }
    end)
    return result
  end)
end

return module
