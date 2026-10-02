-- Shared palette-aware Filter execution; callers own their native adjustment.
local module = {}
local json_null = json.decode("null")
local support = dofile(app.params.filter_support)
local digest = dofile(app.params.digest)
local palette = dofile(app.params.palette)
local effective = dofile(app.params.effective_palette)
local persistence = dofile(app.params.persistence)

function module.apply(sprite, payload, uuids, title, adjust, tiles, preflight)
  local application = payload.application or payload
  local application_kind = application.kind or "pixels"
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
      cel_states = {},
    }
  else
    targets, rejection = support.targets(sprite, application.cels_target, uuids, mode, tiles ~= nil)
    if rejection then return rejection end
  end
  local flags, channels = support.channels(application.channels)
  if (flags & FilterChannels.ALPHA) ~= 0 then
    for _, image in ipairs(targets.images) do
      if image.layer.isBackground then
        return support.reject(
          "Background Layer ignores Alpha Channel; convert it before filtering",
          true
        )
      end
    end
  end
  local first = targets.images[1]
  local anchor = first and first.layer:cel(first.frame)
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
    local needs_alpha_anchor = (palette_only or rgb_palette) and (flags & FilterChannels.ALPHA) ~= 0
    for _, cel in ipairs(sprite.cels) do
      if
        cel.frame.frameNumber == frame
        and not cel.layer.isReference
        and (palette_only or tiles ~= nil or not cel.layer.isTilemap)
        and not (needs_alpha_anchor and cel.layer.isBackground)
      then
        anchor = cel
        break
      end
    end
    if not anchor then
      return support.reject(
        needs_alpha_anchor
            and "Palette Alpha requires a non-Background image anchor at the Palette basis Frame"
          or "Palette basis Frame has no native-safe image anchor",
        true
      )
    end
  end
  local palette_before = palette.list(sprite)
  table.sort(picks)
  local before = palette_only and support.snapshot(sprite, uuids, true)
  return support.with_state(sprite, function()
    app.activeSprite = sprite
    local tile_anchor = tiles and tiles.anchor(targets)
    if tile_anchor then
      app.activeCel = tile_anchor
      local refused =
        tiles.admit(application, payload.tilemap_manual_filter_available, app.site.tilesetMode)
      if refused then return support.reject(refused, true) end
    end
    app.activeCel = anchor
    -- Verify the command's actual Site too, including an explicit Palette anchor.
    if tile_anchor then
      local refused =
        tiles.admit(application, payload.tilemap_manual_filter_available, app.site.tilesetMode)
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
    if preflight then
      local refused = preflight(targets, basis, sprite.selection, anchor)
      if refused then return refused end
    end
    local result
    local tile_before = tiles and tiles.snapshot(sprite, mode)
    local metadata_before = tile_anchor and tiles.serialized_metadata(sprite)
    app.transaction(title, function()
      local filtering = adjust(flags, targets)
      local images, processed, changed = {}, {}, false
      for number, image in ipairs(targets.images) do
        if filtering then processed[#processed + 1] = number end
        local cel = image.layer:cel(image.frame)
        local after = cel and digest.image_content(cel.image, image.mode) or json_null
        local differs = not cel or image.before.value ~= after.value
        changed = changed or differs
        images[#images + 1] = {
          image_number = number,
          before_content_digest = image.before,
          after_content_digest = after,
          changed = differs,
        }
        if tiles then images[#images].image_kind = image.image_kind end
      end
      local cel_effects = {}
      for index, state in ipairs(targets.cel_states) do
        local fact = targets.affected_cels[index]
        local cel = state.layer:cel(state.frame)
        local bounds = cel and cel.bounds
        local after = cel
            and {
              x = bounds.x,
              y = bounds.y,
              width = bounds.width,
              height = bounds.height,
            }
          or json_null
        changed = changed or not persistence.equal(state.before, after)
        cel_effects[#cel_effects + 1] = {
          layer_path = fact.layer_path,
          frame_number = fact.frame_number,
          image_number = fact.image_number,
          before = state.before,
          after = after,
        }
      end
      local palette_after = palette.list(sprite)
      local changed_tiles
      if tiles then
        changed_tiles = tiles.changes(tile_before, tiles.snapshot(sprite, mode), targets)
        if metadata_before then
          assert(
            persistence.equal(metadata_before, tiles.serialized_metadata(sprite)),
            "Filter User Data changed"
          )
        end
        changed = changed or #changed_tiles > 0
      end
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
        application = application_kind,
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
        changed = changed,
        requested_intersections = targets.requested_intersections,
        existing_target_cels = targets.existing_target_cels,
        excluded_layers = targets.excluded_layers,
        affected_cels = targets.affected_cels,
        cel_effects = cel_effects,
      }
      if tiles then
        result.requested_tileset_mode = application.tileset_mode or json_null
        result.observed_tileset_mode = tile_anchor and "manual" or json_null
        result.changed_tiles = changed_tiles
      end
    end)
    return result
  end)
end

-- Fixed-pixel Operations share execution mechanics without exposing Palette
-- mutation application modes in their public requests or results.
function module.apply_pixels(sprite, payload, uuids, title, adjust)
  local result = module.apply(sprite, {
    application = {
      kind = "pixels",
      color_mode = payload.color_mode,
      channels = payload.channels,
      cels_target = payload.cels_target,
      selection = payload.selection,
      palette_frame_number = payload.palette_frame_number,
    },
  }, uuids, title, adjust)
  result.application = nil
  result.palette_indexes = nil
  return result
end

return module
