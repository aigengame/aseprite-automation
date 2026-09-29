-- Native Paint composition and explicit Image/Selection coverage.
local module = {}
local snapshot = dofile(app.params.image_snapshot)
local selections = dofile(app.params.selection_mask)
local colors = dofile(app.params.raster_color)
local palettes = dofile(app.params.effective_palette)

local modes = {
  normal = BlendMode.NORMAL,
  multiply = BlendMode.MULTIPLY,
  screen = BlendMode.SCREEN,
  overlay = BlendMode.OVERLAY,
  darken = BlendMode.DARKEN,
  lighten = BlendMode.LIGHTEN,
  ["color-dodge"] = BlendMode.COLOR_DODGE,
  ["color-burn"] = BlendMode.COLOR_BURN,
  ["hard-light"] = BlendMode.HARD_LIGHT,
  ["soft-light"] = BlendMode.SOFT_LIGHT,
  difference = BlendMode.DIFFERENCE,
  exclusion = BlendMode.EXCLUSION,
  hue = BlendMode.HUE,
  saturation = BlendMode.SATURATION,
  color = BlendMode.COLOR,
  luminosity = BlendMode.LUMINOSITY,
  addition = BlendMode.ADDITION,
  subtract = BlendMode.SUBTRACT,
  divide = BlendMode.DIVIDE,
}

function module.draw(destination, source, position, opacity, blend_mode)
  local mode = assert(modes[blend_mode], "unsupported native BlendMode")
  assert(blend_mode == "normal" or mode ~= BlendMode.NORMAL, "BlendMode aliases Normal")
  assert(opacity % 1 == 0 and opacity >= 0 and opacity <= 255, "invalid opacity")
  local result = Image(destination)
  -- Aseprite checks lua_isinteger here; JSON numbers otherwise select its 255 default.
  result:drawImage(source, Point(position.x, position.y), assert(math.tointeger(opacity)), mode)
  return result
end

function module.draw_indexed(destination, source, position, palette)
  local previous = { sprite = app.activeSprite, layer = app.activeLayer, frame = app.activeFrame }
  local scratch = nil
  local ok, result = pcall(function()
    scratch = Sprite(destination.width, destination.height, ColorMode.INDEXED)
    scratch.transparentColor = destination.spec.transparentColor
    scratch:setPalette(palette)
    app.activeSprite = scratch
    local cel = assert(scratch.layers[1]:cel(1))
    cel.image = Image(destination)
    -- Keep the destination associated with the temporary Cel: the native binding
    -- reads its Sprite's first Palette, which is the requested Effective Palette.
    cel.image:drawImage(source, Point(position.x, position.y), 255, BlendMode.NORMAL)
    return Image(cel.image)
  end)
  if scratch ~= nil then scratch:close() end
  if previous.sprite ~= nil and previous.sprite.isValid then
    app.activeSprite, app.activeLayer, app.activeFrame =
      previous.sprite, previous.layer, previous.frame
  end
  if not ok then error(result) end
  return result
end

local function append(runs, x, y)
  local prior = runs[#runs]
  if prior ~= nil and prior.y == y and prior.x + prior.length == x then
    prior.length = prior.length + 1
  else
    runs[#runs + 1] = { x = x, y = y, length = 1 }
  end
end

function module.compose(image, cel, payload, sprite, affected)
  local source, used = snapshot.materialize(payload.input.snapshot, image.spec, false)
  assert(source.colorMode == image.colorMode, "Source and target Color Modes must match")
  local palette = nil
  if image.colorMode == ColorMode.INDEXED then
    assert(
      payload.palette_frame_number == payload.target.frame_number,
      "Indexed composition requires the target Frame Palette"
    )
    assert(
      payload.blend_mode == "normal" and payload.opacity == 255,
      "Indexed composition supports only Normal at opacity 255"
    )
    palette = assert(
      palettes.resolve(sprite, payload.palette_frame_number),
      "Indexed target has no Effective Palette"
    )
    used[image.spec.transparentColor] = true
    for index, _ in pairs(used) do
      assert(index < #palette, "Source or transparent index is absent from the Effective Palette")
    end
  end
  local position = payload.position
  assert(position.x % 1 == 0 and position.y % 1 == 0, "position must use integer Image Pixels")
  local area = { x = position.x, y = position.y, width = source.width, height = source.height }
  local left, top = math.max(0, area.x), math.max(0, area.y)
  local right, bottom =
    math.min(image.width, area.x + area.width), math.min(image.height, area.y + area.height)
  assert(payload.clipping == "reject" or payload.clipping == "clip", "invalid clipping")
  if payload.clipping == "reject" then
    assert(
      left == area.x
        and top == area.y
        and right == area.x + area.width
        and bottom == area.y + area.height,
      "Composite Rectangle is outside Image bounds"
    )
  end
  local mask = payload.selection ~= nil and selections.materialize(payload.selection) or nil
  local result = Image(image)
  if right > left and bottom > top then
    -- Only bounded Image coordinates reach Aseprite's 32-bit Point constructor.
    -- A wholly clipped request remains a no-op even for a large declared position.
    local visible =
      Image(source, Rectangle(left - area.x, top - area.y, right - left, bottom - top))
    if palette ~= nil then
      result = module.draw_indexed(image, visible, { x = left, y = top }, palette)
    else
      result =
        module.draw(image, visible, { x = left, y = top }, payload.opacity, payload.blend_mode)
    end
  end
  local applied, bounds, excluded = {}, {}, {}
  local written, changed, skipped_bounds, skipped_selection = 0, 0, 0, 0
  local min_x, min_y, max_x, max_y = nil, nil, nil, nil
  for source_y = 0, source.height - 1 do
    local y = area.y + source_y
    for source_x = 0, source.width - 1 do
      local x = area.x + source_x
      if x < 0 or y < 0 or x >= image.width or y >= image.height then
        append(bounds, x, y)
        skipped_bounds = skipped_bounds + 1
      elseif mask ~= nil and not mask:contains(Point(x + cel.position.x, y + cel.position.y)) then
        append(excluded, x, y)
        skipped_selection = skipped_selection + 1
        result:putPixel(x, y, image:getPixel(x, y))
      else
        append(applied, x, y)
        written = written + 1
        if result:getPixel(x, y) ~= image:getPixel(x, y) then changed = changed + 1 end
        min_x, min_y = math.min(min_x or x, x), math.min(min_y or y, y)
        max_x, max_y = math.max(max_x or x + 1, x + 1), math.max(max_y or y + 1, y + 1)
      end
    end
  end
  local palette_basis, effective_palettes = json.decode("null"), {}
  if palette ~= nil then
    local output_indexes = {}
    for pixel in result:pixels() do
      output_indexes[pixel()] = true
      used[pixel()] = true
    end
    palette_basis =
      colors.palette_facts(sprite, { { frame_number = payload.target.frame_number } }, used)[1]
    effective_palettes = colors.palette_facts(sprite, affected, output_indexes)
    for _, state in ipairs(affected) do
      if state.is_background then
        for _, fact in ipairs(effective_palettes) do
          if fact.frame_number == state.frame_number then
            for _, index in ipairs(fact.indexes) do
              assert(index.color.alpha == 255, "Background Palette colors must remain opaque")
            end
          end
        end
      end
    end
  end
  return result,
    {
      input_form = payload.input.kind,
      color_mode = snapshot.mode(image),
      position = { x = position.x, y = position.y },
      opacity = payload.opacity,
      blend_mode = payload.blend_mode,
      clipping = payload.clipping,
      selection = selections.copy_value(payload.selection),
      source_rectangle = snapshot.rectangle(payload.input.snapshot.rectangle),
      target_rectangle = area,
      clipped_rectangle = {
        x = left,
        y = top,
        width = math.max(0, right - left),
        height = math.max(0, bottom - top),
      },
      applied_rectangle = {
        x = min_x or area.x,
        y = min_y or area.y,
        width = min_x and max_x - min_x or 0,
        height = min_y and max_y - min_y or 0,
      },
      applied_runs = applied,
      skipped_by_bounds_runs = bounds,
      skipped_by_selection_runs = excluded,
      pixels_requested = source.width * source.height,
      pixels_written = written,
      pixels_changed = changed,
      pixels_skipped_by_bounds = skipped_bounds,
      pixels_skipped_by_selection = skipped_selection,
      composite_palette_basis = palette_basis,
      effective_palettes = effective_palettes,
    }
end

return module
