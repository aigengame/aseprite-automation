-- Delivery owns sample selection and projection; existing native owners render and encode.
local module = {}
local composition = dofile(assert(app.params.layer_composition))
local layers = dofile(assert(app.params.layer_select))
local tags = dofile(assert(app.params.tag_select))
local palettes = dofile(assert(app.params.effective_palette))
local profiles = dofile(assert(app.params.color_profile))
local inspection = dofile(assert(app.params.inspection))
local null = json.decode("null")
local max_pixels = 16777216
local max_side = 65535

local function reject(reason, message) return { rejection = { reason = reason, message = message } } end
local function rectangle(value)
  return { x = value.x, y = value.y, width = value.width, height = value.height }
end
local function palette_values(palette)
  local values, bytes = {}, {}
  for index = 0, #palette - 1 do
    local color = palette:getColor(index)
    values[#values + 1] = { color.red, color.green, color.blue, color.alpha }
    bytes[#bytes + 1] = string.pack("BBBB", color.red, color.green, color.blue, color.alpha)
  end
  return values, table.concat(bytes)
end
local function range(source, value)
  if value.kind == "tag" then
    local tag, index, code, message = tags.resolve(source, value.tag)
    if tag == nil then return nil, nil, nil, reject(code, message) end
    return tag.fromFrame.frameNumber, tag.toFrame.frameNumber, index
  end
  assert(value.kind == "range", "unsupported selection kind")
  local first, last = value.from_frame, value.to_frame
  if first < 1 or last < first or last > #source.frames then
    return nil,
      nil,
      nil,
      reject("frame_range", "Frame Range must be ordered and within the Source timeline")
  end
  return first, last
end
local function background(source, resolved)
  for _, path in ipairs(resolved) do
    local siblings, layer = source.layers, nil
    for _, index in ipairs(path) do
      layer = siblings[index]
      if layer.isGroup then siblings = layer.layers end
    end
    if layer.isBackground then return true end
  end
  return false
end
local function native_export(sprite, payload, image, metadata, first, last, kind, trim, padding)
  local types = {
    horizontal = SpriteSheetType.HORIZONTAL,
    vertical = SpriteSheetType.VERTICAL,
    rows = SpriteSheetType.ROWS,
    columns = SpriteSheetType.COLUMNS,
    packed = SpriteSheetType.PACKED,
  }
  app.activeSprite = sprite
  local selected = {}
  for number = first, last do
    selected[#selected + 1] = number
  end
  app.range.frames = selected
  assert(#app.range.frames == #selected, "native Frame selection differs")
  app.command.ExportSpriteSheet {
    ui = false,
    recent = false,
    askOverwrite = false,
    type = assert(types[kind]),
    textureFilename = image,
    dataFilename = metadata,
    dataFormat = SpriteSheetDataFormat.JSON_ARRAY,
    tag = "**selected-frames**",
    filenameFormat = payload.filename_format,
    listTags = true,
    listLayers = false,
    listLayerHierarchy = false,
    listSlices = false,
    splitLayers = false,
    splitTags = false,
    splitGrid = false,
    fromTilesets = false,
    powerOfTwoSize = false,
    tagnameFormat = "{tag}",
    layer = "",
    trim = trim == "frame",
    trimSprite = trim == "sprite",
    trimByGrid = false,
    ignoreEmpty = false,
    mergeDuplicates = true,
    extrude = false,
    borderPadding = padding.border,
    shapePadding = padding.shape,
    innerPadding = padding.inner,
    columns = kind == "rows" and payload.layout.columns or 0,
    rows = kind == "columns" and payload.layout.rows or 0,
    width = 0,
    height = 0,
    bestFit = false,
  }
end
local function read_json(path)
  local file = assert(io.open(path, "rb"), "native metadata is missing")
  local value = json.decode(file:read("a"))
  file:close()
  return value
end
local function common_trim(sprite, payload, first)
  local image = assert(payload.staged_trim_png_file)
  local metadata = assert(payload.staged_trim_metadata_file)
  local ok, result = pcall(function()
    native_export(sprite, payload, image, metadata, first, first, "horizontal", "sprite", {
      border = 0,
      shape = 0,
      inner = 0,
    })
    local frame = assert(read_json(metadata).frames[1], "native trim sample is missing")
    local bounds = assert(frame.spriteSourceSize)
    return { x = bounds.x, y = bounds.y, width = bounds.w, height = bounds.h }
  end)
  os.remove(image)
  os.remove(metadata)
  if not ok then error(result) end
  return result
end
local function trim_bounds(image, has_background, mode, common)
  if mode == "sprite" then return common end
  if mode == "none" then return { x = 0, y = 0, width = image.width, height = image.height } end
  local reference = has_background and image:getPixel(0, 0) or image.spec.transparentColor
  local bounds = image:shrinkBounds(reference)
  if bounds.isEmpty then return { x = 0, y = 0, width = 1, height = 1 } end
  return rectangle(bounds)
end
local function check_allocation_limits(source, first, last, payload)
  local count = last - first + 1
  local timeline_count = payload.trim == "sprite" and #source.frames or count
  if source.width * source.height * timeline_count > max_pixels then
    return reject(
      "allocation_limit",
      "Rendered timeline requests "
        .. (source.width * source.height * timeline_count)
        .. " Pixels; current allowed maximum is 16777216"
    )
  end
  local cell_w = source.width + 2 * payload.padding.inner
  local cell_h = source.height + 2 * payload.padding.inner
  local cols, rows = count, 1
  if payload.layout.kind == "vertical" then
    cols, rows = 1, count
  elseif payload.layout.kind == "rows" then
    cols = math.min(count, payload.layout.columns)
    rows = math.ceil(count / cols)
  elseif payload.layout.kind == "columns" then
    rows = math.min(count, payload.layout.rows)
    cols = math.ceil(count / rows)
  elseif payload.layout.kind == "packed" then
    -- Bound both axes by the sum of all untrimmed sample extents. This deliberately
    -- conservative allocation guard does not predict or replace native packing.
    cols, rows = count, count
  end
  local width = cols * cell_w + (cols - 1) * payload.padding.shape + 2 * payload.padding.border
  local height = rows * cell_h + (rows - 1) * payload.padding.shape + 2 * payload.padding.border
  if width > max_side or height > max_side or width * height > max_pixels then
    return reject(
      "allocation_limit",
      "Conservative untrimmed sheet bound is "
        .. width
        .. "x"
        .. height
        .. "; current allowed maximum is 65535 per side and 16777216 Pixels"
    )
  end
end
local function run(source, disposable, payload, profile, first, last, selected_index)
  local uuids = inspection.saved_layer_uuids(source, payload.source_sprite_file)
  if payload.layer_composition.mode == "include" then
    for _, address in ipairs(payload.layer_composition.layers) do
      local selected, code, message = layers.resolve(source, address, uuids)
      if selected == nil then return reject(code, message) end
      if selected.layer.isReference then
        return reject("reference_layer", "Direct Reference Layer selection is unsupported")
      end
    end
  end
  local palette, values, palette_bytes
  if payload.output_color_mode == "indexed" then
    if source.colorMode ~= ColorMode.INDEXED then
      return reject("source_color_mode", "Indexed output requires an Indexed Source Sprite")
    end
    for number = first, last do
      local effective = palettes.resolve(source, number)
      if
        effective == nil
        or #effective < 1
        or #effective > 256
        or source.transparentColor >= #effective
      then
        return reject(
          "palette",
          "Indexed output requires 1-256 complete Palette entries and a defined Transparent Color Index"
        )
      end
      local current_values, current_bytes = palette_values(effective)
      if palette_bytes ~= nil and palette_bytes ~= current_bytes then
        return reject(
          "palette_mismatch",
          "Selected Frames have different complete Effective Palettes"
        )
      end
      palette, values, palette_bytes = effective, current_values, current_bytes
    end
    disposable:setPalette(palette)
    disposable.transparentColor = source.transparentColor
  end
  local export_space = ColorSpace(source.colorSpace)
  if profile.kind == "icc" then
    -- PNG needs a nonempty iCCP keyword. A headless backend can leave the native
    -- display name empty; name this copy without changing the embedded ICC bytes.
    export_space.name = assert(profile.icc_identity)
  end
  disposable:assignColorSpace(export_space)
  disposable:deleteCel(disposable.layers[1], 1)
  local all_tags = inspection.inspect(source, { "tags" }, uuids).tags
  local source_tags, projected_tags = {}, {}
  for index, facts in ipairs(all_tags) do
    facts.tag_index = index
    source_tags[#source_tags + 1] = facts
    if facts.from_frame >= first and facts.to_frame <= last then
      projected_tags[#projected_tags + 1] = {
        source_tag_index = index,
        name = facts.name,
        from = facts.from_frame - first,
        to = facts.to_frame - first,
        direction = facts.direction,
        repeats = facts.repeats,
        color = facts.color,
      }
    end
  end
  local selected_images, frame_facts, source_frames = {}, {}, {}
  local timeline_bytes = {}
  local resolved, has_background
  local render_first = payload.trim == "sprite" and 1 or first
  local render_last = payload.trim == "sprite" and #source.frames or last
  for number = render_first, render_last do
    local image, paths, failure = composition.render(
      source,
      number,
      payload.layer_composition,
      { x = 0, y = 0, width = source.width, height = source.height },
      layers,
      uuids,
      payload.output_color_mode == "rgb" and "rgb" or "preserve"
    )
    if failure then return reject(failure.rejection.code, failure.rejection.message) end
    resolved = paths
    has_background = background(source, paths)
    if number >= first and number <= last then
      if palette ~= nil then
        local missing = composition.missing_output_index(image, palette)
        if missing then return reject("palette", missing.rejection.message) end
      end
      selected_images[#selected_images + 1] = image
      source_frames[#source_frames + 1] = number
    end
    local output_number = number - render_first + 1
    if output_number > 1 then disposable:newEmptyFrame() end
    disposable:newCel(disposable.layers[1], output_number, image, Point(0, 0))
    timeline_bytes[output_number] = image.bytes
    disposable.frames[output_number].duration = source.frames[number].duration
  end
  if has_background then
    app.activeSprite = disposable
    app.activeLayer = disposable.layers[1]
    app.activeFrame = disposable.frames[1]
    app.command.BackgroundFromLayer()
    assert(disposable.layers[1].isBackground, "native Background context was not retained")
    -- Configure the native trim context without letting Background conversion fill samples.
    for number, bytes in ipairs(timeline_bytes) do
      disposable.layers[1]:cel(number).image.bytes = bytes
    end
  end
  for _, projected in ipairs(projected_tags) do
    local original = source.tags[projected.source_tag_index]
    local copy = disposable:newTag(projected.from + 1, projected.to + 1)
    copy.name, copy.aniDir, copy.repeats, copy.color =
      original.name, original.aniDir, original.repeats, original.color
  end
  local output_first, output_last = first - render_first + 1, last - render_first + 1
  local common = payload.trim == "sprite" and common_trim(disposable, payload, output_first) or nil
  local pixels_file = assert(io.open(payload.staged_pixels_file, "wb"))
  local offset = 0
  for ordinal, image in ipairs(selected_images) do
    local bounds = trim_bounds(image, has_background, payload.trim, common)
    if palette ~= nil and has_background then
      local visual, _, failure = composition.render(
        source,
        source_frames[ordinal],
        payload.layer_composition,
        { x = 0, y = 0, width = source.width, height = source.height },
        layers,
        uuids,
        "rgb"
      )
      assert(failure == nil, "native Background alpha observation failed")
      for y = bounds.y, bounds.y + bounds.height - 1 do
        for x = bounds.x, bounds.x + bounds.width - 1 do
          if
            image:getPixel(x, y) == source.transparentColor
            and app.pixelColor.rgbaA(visual:getPixel(x, y)) > 0
          then
            pixels_file:close()
            return reject(
              "background_transparency",
              "Retained Background pixels use the PNG Transparent Color Index"
            )
          end
        end
      end
    end
    local bytes = image.bytes
    assert(
      #bytes == source.width * source.height * (palette and 1 or 4),
      "unexpected native Image layout"
    )
    assert(pixels_file:write(bytes))
    frame_facts[#frame_facts + 1] = {
      frame_number = source_frames[ordinal],
      duration_ms = math.floor(source.frames[source_frames[ordinal]].duration * 1000 + 0.5),
      trim = bounds,
      pixels_offset = offset,
      pixels_byte_size = #bytes,
    }
    offset = offset + #bytes
  end
  assert(pixels_file:close())
  native_export(
    disposable,
    payload,
    payload.staged_png_file,
    payload.staged_metadata_file,
    output_first,
    output_last,
    payload.layout.kind,
    payload.trim,
    payload.padding
  )
  local metadata = read_json(payload.staged_metadata_file)
  metadata.meta.image = payload.image_reference
  local metadata_file = assert(io.open(payload.staged_metadata_file, "wb"))
  assert(metadata_file:write(json.encode(metadata)))
  assert(metadata_file:close())
  return {
    source_width = source.width,
    source_height = source.height,
    width = metadata.meta.size.w,
    height = metadata.meta.size.h,
    color_mode = payload.output_color_mode,
    color_profile = profile.kind,
    icc_identity = profile.icc_identity or null,
    transparent_index = palette and source.transparentColor or null,
    palette = values or null,
    source_frames = source_frames,
    frames = frame_facts,
    source_tags = source_tags,
    selected_tag = selected_index and source_tags[selected_index] or null,
    common_trim = common or null,
    effective_background = has_background,
    layer_composition = composition.copy(payload.layer_composition),
    resolved_layer_paths = resolved,
    rendered_byte_size = offset,
  }
end
function module.execute(payload)
  assert(
    payload.output_color_mode == "rgb" or payload.output_color_mode == "indexed",
    "explicit output Color Mode is required"
  )
  local source, disposable
  local previous_manage = app.preferences.color.manage
  local previous_embedded = app.preferences.color.files_with_profile
  local previous_missing = app.preferences.color.missing_profile
  local previous_compose = app.preferences.experimental.compose_groups
  local ok, result = pcall(function()
    app.preferences.color.manage = true
    app.preferences.color.files_with_profile = 1
    app.preferences.color.missing_profile = 0
    app.preferences.experimental.compose_groups = true
    source = assert(app.open(payload.source_sprite_file), "could not open Source Sprite File")
    local restored, profile =
      pcall(profiles.restore_file_profile, source, payload.source_sprite_file)
    if not restored or (profile.kind == "icc" and profile.icc_identity == nil) then
      return reject(
        "color_profile",
        "Source Color Profile is outside None, sRGB and the exact supported ICC profiles"
      )
    end
    local first, last, selected_index, rejected = range(source, payload.selection)
    if rejected then return rejected end
    rejected = check_allocation_limits(source, first, last, payload)
    if rejected then return rejected end
    disposable = Sprite(
      source.width,
      source.height,
      payload.output_color_mode == "rgb" and ColorMode.RGB or ColorMode.INDEXED
    )
    return run(source, disposable, payload, profile, first, last, selected_index)
  end)
  if disposable ~= nil then pcall(function() disposable:close() end) end
  if source ~= nil then pcall(function() source:close() end) end
  app.preferences.color.manage = previous_manage
  app.preferences.color.files_with_profile = previous_embedded
  app.preferences.color.missing_profile = previous_missing
  app.preferences.experimental.compose_groups = previous_compose
  if not ok then error(result) end
  return result
end
-- Structural runtime capability evidence; feature combinations are verified by public tests.
function module.observe(workspace)
  local sprite = Sprite(2, 1, ColorMode.RGB)
  local image_path = workspace .. "/sheet-capability.png"
  local metadata_path = workspace .. "/sheet-capability.json"
  local ok, observed = pcall(function()
    sprite.layers[1]:cel(1).image:drawPixel(0, 0, app.pixelColor.rgba(201, 17, 29, 255))
    sprite:newEmptyFrame()
    local image = Image(2, 1, ColorMode.RGB)
    image:drawPixel(1, 0, app.pixelColor.rgba(31, 100, 151, 255))
    sprite:newCel(sprite.layers[1], 2, image)
    sprite.frames[1].duration, sprite.frames[2].duration = 0.07, 0.11
    native_export(
      sprite,
      { filename_format = "{frame1}", layout = { kind = "horizontal" } },
      image_path,
      metadata_path,
      1,
      2,
      "horizontal",
      "none",
      { border = 0, shape = 0, inner = 0 }
    )
    local file = assert(io.open(image_path, "rb"))
    local signature = file:read(8)
    file:close()
    local metadata = read_json(metadata_path)
    return signature == "\137PNG\r\n\26\n"
      and #metadata.frames == 2
      and metadata.frames[1].duration == 70
      and metadata.frames[2].duration == 110
      and metadata.meta.size.w == 4
      and metadata.meta.size.h == 1
  end)
  sprite:close()
  os.remove(image_path)
  os.remove(metadata_path)
  return ok and observed == true
end
return module
