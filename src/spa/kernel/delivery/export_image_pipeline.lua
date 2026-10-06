-- Static delivery composes existing native owners on one disposable Sprite.
local module = {}
local composition = dofile(app.params.layer_composition)
local selection = dofile(app.params.layer_select)
local inspection = dofile(app.params.inspection)
local slices = dofile(app.params.slice)
local profiles = dofile(app.params.color_profile)
local palettes = dofile(app.params.effective_palette)
local palette_file = dofile(app.params.palette_file)
local quantization = dofile(app.params.palette_quantization)
local modes = dofile(app.params.color_mode)
local layers = dofile(app.params.layer_mutation)
local frames = dofile(app.params.frame)
local persistence = dofile(app.params.persistence)
local digest = dofile(app.params.digest)
local images = dofile(app.params.export_image_support)

local function mode(value)
  return assert(
    ({
      [ColorMode.RGB] = "rgb",
      [ColorMode.GRAY] = "grayscale",
      [ColorMode.INDEXED] = "indexed",
    })[value.colorMode],
    "unsupported native Color Mode"
  )
end

local function reject(reason, message)
  return { rejection = { code = "export_image_invalid", reason = reason, message = message } }
end

local function copy_rectangle(value)
  return { x = value.x, y = value.y, width = value.width, height = value.height }
end

local function area(source, input, number)
  local result = { kind = input.kind }
  if input.kind == "canvas" then
    result.rectangle = { x = 0, y = 0, width = source.width, height = source.height }
  elseif input.kind == "rectangle" then
    result.rectangle = copy_rectangle(input.rectangle)
  else
    assert(input.kind == "slice", "unsupported Export Image Area")
    local selected, index, code, message = slices.resolve(source, input.slice)
    if not selected then return nil, { rejection = { code = code, message = message } } end
    local fact = slices.snapshot(source, inspection).slices[index]
    local effective
    for _, key in ipairs(fact.keys) do
      if key.frame_number <= number then effective = key end
    end
    if not effective then
      return nil, reject("slice_key", "The selected Slice has no effective Key at the Frame")
    end
    result.rectangle = copy_rectangle(effective.bounds)
    result.slice_index, result.slice_name = index, fact.name
    result.key_frame_number = effective.frame_number
  end
  local rectangle = result.rectangle
  if
    rectangle.width <= 0
    or rectangle.height <= 0
    or rectangle.x < 0
    or rectangle.y < 0
    or rectangle.x + rectangle.width > source.width
    or rectangle.y + rectangle.height > source.height
  then
    return nil, reject("area", "Export Image Area must be a positive Rectangle inside the Canvas")
  end
  return result
end

local function palette_preparation(working, input)
  if input.kind == "current" then return {} end
  if input.kind == "import" then
    return palette_file.import(working, {
      palette_frame_number = "1",
      palette_file = input.palette_file,
      palette_file_bytes = input.palette_file_bytes,
    }, {})
  end
  assert(input.kind == "quantize", "unsupported Palette preparation")
  return quantization.apply(working, {
    palette_frame_number = "1",
    max_colors = tostring(input.max_colors),
    with_alpha = input.with_alpha,
    rgb_map_algorithm = input.rgb_map_algorithm,
    new_layer_blending_method = input.new_layer_blending_method,
  }, {})
end

local function encoded_palette(working, image, background)
  if working.colorMode ~= ColorMode.INDEXED then return nil end
  local palette = palettes.resolve(working, 1)
  local mask = working.transparentColor
  if not palette or #palette < 1 or #palette > 256 or mask < 0 or mask >= #palette then
    return nil,
      reject(
        "palette",
        "Indexed PNG requires 1-256 complete Palette entries and its Transparent Color Index"
      )
  end
  local missing = composition.missing_output_index(image, palette)
  if missing then return nil, reject("palette", missing.rejection.message) end
  local result = {}
  for index = 0, #palette - 1 do
    local color = palette:getColor(index)
    result[#result + 1] = {
      red = color.red,
      green = color.green,
      blue = color.blue,
      alpha = not background and index == mask and 0 or color.alpha,
    }
  end
  return result
end

local function rgba(image, palette)
  local result, minimum, maximum = {}, 255, 0
  for pixel in image:pixels() do
    local value = pixel()
    local red, green, blue, alpha
    if image.colorMode == ColorMode.RGB then
      red, green, blue, alpha =
        app.pixelColor.rgbaR(value),
        app.pixelColor.rgbaG(value),
        app.pixelColor.rgbaB(value),
        app.pixelColor.rgbaA(value)
    elseif image.colorMode == ColorMode.GRAY then
      red, alpha = app.pixelColor.grayaV(value), app.pixelColor.grayaA(value)
      green, blue = red, red
    else
      local color = assert(palette[value + 1], "PNG Palette omits a stored index")
      red, green, blue, alpha = color.red, color.green, color.blue, color.alpha
    end
    result[#result + 1] = string.pack("BBBB", red, green, blue, alpha)
    minimum, maximum = math.min(minimum, alpha), math.max(maximum, alpha)
  end
  return table.concat(result), minimum, maximum
end

local function write_bytes(path, bytes)
  local file = assert(io.open(path, "wb"))
  assert(file:write(bytes))
  assert(file:close())
end

function module.execute(payload)
  local source, working, before, uuids
  local previous = {
    sprite = app.activeSprite,
    layer = app.activeLayer,
    frame = app.activeFrame,
    foreground = app.fgColor,
    background = app.bgColor,
    compose_groups = app.preferences.experimental.compose_groups,
  }
  local ok, result = pcall(function()
    source = assert(app.open(payload.source_sprite_file), "could not open Source Sprite")
    local profile = profiles.restore_file_profile(source, payload.source_sprite_file)
    if profile.kind == "icc" and not profile.icc_identity then
      return reject(
        "color_profile",
        "Only the packaged linear-sRGB and Display P3 ICC identities are supported"
      )
    end
    uuids = inspection.saved_layer_uuids(source, payload.source_sprite_file)
    before = profiles.snapshot(source, uuids)
    local number = payload.frame_number
    if number < 1 or number > #source.frames then
      return reject("frame_number", "Frame Number exceeds the Source timeline")
    end
    local resolved_area, failed = area(source, payload.export_image_area, number)
    if failed then return failed end
    local context
    context, failed = composition.resolve(source, payload.layer_composition, selection, uuids)
    if failed then return failed end
    if context.direct_reference then
      return reject("layer_composition", "Direct inclusion of a Reference Layer is unsupported")
    end
    local rendered, paths, background
    rendered, paths, failed, background = composition.render(
      source,
      number,
      payload.layer_composition,
      resolved_area.rectangle,
      selection,
      uuids,
      payload.composition_color_mode
    )
    if failed then return failed end
    local composed_mode = mode(rendered)
    working = Sprite(ImageSpec(rendered.spec))
    local current = palettes.resolve(source, number)
    if current then working:setPalette(Palette(current)) end
    working:assignColorSpace(source.colorSpace)
    app.activeSprite, app.activeLayer, app.activeFrame =
      working, working.layers[1], working.frames[1]
    if background then
      -- Retain native encoding context before attaching the composed samples.
      app.command.BackgroundFromLayer { ui = false }
      assert(working.layers[1].isBackground, "native Background context was not retained")
    end
    working.cels[1].image = rendered
    local state = {
      kind = profile.kind,
      profile = working.colorSpace,
      icc_identity = profile.icc_identity,
      icc_color_space = profile.icc_color_space,
    }
    if payload.color_profile ~= "preserve" then
      local changed =
        profiles.apply_live(working, payload.color_profile.kind, payload.color_profile, {}, state)
      if changed.rejection then return changed end
      state.kind = changed.effective_profile.kind
    end
    local conversion = payload.color_mode
    local maps_to_indexed = conversion ~= "preserve"
      and composed_mode ~= "indexed"
      and conversion.target.color_mode == "indexed"
    if maps_to_indexed then
      if not payload.palette_preparation then
        return reject(
          "palette_preparation",
          "Conversion to Indexed requires explicit Palette preparation"
        )
      end
      local prepared = palette_preparation(working, payload.palette_preparation)
      if prepared.rejection then return prepared end
    elseif payload.palette_preparation ~= nil then
      return reject(
        "palette_preparation",
        "Palette preparation applies only to non-Indexed conversion to Indexed"
      )
    end
    if conversion ~= "preserve" then
      local changed = modes.change(working, conversion)
      if changed.rejection then return changed end
    end
    if working.colorMode == ColorMode.GRAY and state.kind == "icc" then
      return reject("color_profile", "Grayscale PNG does not support the admitted RGB ICC profiles")
    end
    if payload.transparency ~= "preserve" then
      assert(payload.transparency.kind == "background", "unsupported transparency choice")
      local changed, failure = pcall(function()
        local layer = working.layers[1]
        if layer.isBackground then layers.convert_from_background(working, layer) end
        layers.convert_to_background(working, layer, payload.transparency.background_color, frames)
      end)
      if not changed then return reject("background", tostring(failure)) end
    end
    local image = working.cels[1].image
    background = working.layers[1].isBackground
    local entries
    entries, failed = encoded_palette(working, image, background)
    if failed then return failed end
    local bytes, minimum, maximum = rgba(image, entries)
    if payload.transparency ~= "preserve" and minimum ~= 255 then
      return reject("background", "Native Background contains non-opaque output pixels")
    end
    assert(image.rowStride == image.width * image.bytesPerPixel, "unexpected native Image layout")
    local facts = {
      frame_number = number,
      width = image.width,
      height = image.height,
      source_color_mode = mode(source),
      composition_color_mode = payload.composition_color_mode,
      source_canvas = { width = source.width, height = source.height },
      export_image_area = resolved_area,
      resolved_layer_paths = paths,
      effective_background = background,
      color_mode = mode(image),
      color_profile = state.kind,
      icc_identity = state.icc_identity,
      transparent_index = working.colorMode == ColorMode.INDEXED and working.transparentColor
        or nil,
      palette_entries = entries,
      alpha_min = minimum,
      alpha_max = maximum,
      rendered_byte_size = #bytes,
      stored_content_digest = digest.fnv1a64(image.bytes),
    }
    write_bytes(payload.staged_rgba_file, bytes)
    working:assignColorSpace(images.png_color_space(working.colorSpace, state))
    app.activeSprite, app.activeLayer, app.activeFrame =
      working, working.layers[1], working.frames[1]
    -- Keep arbitrary destination text out of Aseprite's Filename Format parser.
    local native_png = app.params.workspace .. "/export-image.png"
    app.command.SaveFileCopyAs {
      ui = false,
      filename = native_png,
      ignoreEmpty = false,
    }
    local encoded = assert(io.open(native_png, "rb"), "native PNG encoding produced no file")
    local encoded_bytes = assert(encoded:read("a"))
    encoded:close()
    write_bytes(payload.staged_png_file, encoded_bytes)
    return facts
  end)
  if source and before then
    local unchanged, failure = pcall(
      function() persistence.assert_equal(before, profiles.snapshot(source, uuids), "Export Source") end
    )
    if not unchanged then
      ok, result = false, failure
    end
  end
  if working then pcall(function() working:close() end) end
  if source then pcall(function() source:close() end) end
  if previous.sprite and previous.sprite.isValid then
    pcall(function() app.activeSprite = previous.sprite end)
    pcall(function() app.activeLayer = previous.layer end)
    pcall(function() app.activeFrame = previous.frame end)
  end
  pcall(function() app.fgColor = previous.foreground end)
  pcall(function() app.bgColor = previous.background end)
  pcall(function() app.preferences.experimental.compose_groups = previous.compose_groups end)
  if not ok then error(result, 0) end
  return result
end

return module
