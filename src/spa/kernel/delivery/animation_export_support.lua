-- Asset Delivery owns playback and encoding; rendering/profile semantics use their owners.
local module = {}
local composition = dofile(app.params.layer_composition)
local selection = dofile(app.params.layer_select)
local inspection = dofile(app.params.inspection)
local profiles = dofile(app.params.color_profile)
local tags = dofile(app.params.tag_select)
local palettes = dofile(app.params.effective_palette)
local gif = dofile(app.params.animation_gif)
local null = json.decode("null")

local function reject(reason, message) return { rejection = { reason = reason, message = message } } end

local function filenames(format, count)
  local prefix, digits, suffix = format:match("^([^{}]*){frame(0*[01])}([^{}]*)$")
  if
    not prefix
    or tonumber(digits) > 1
    or #digits > 9
    or format:find("[/\\%z\r\n]")
    or suffix:sub(-4) ~= ".png"
  then
    return nil,
      reject(
        "filename_format",
        "Use one {frame0} or {frame1} ordinal (up to 9 digits), literal prefix/suffix, and .png"
      )
  end
  local result = {}
  for occurrence = 1, count do
    result[occurrence] = prefix
      .. string.format("%0" .. #digits .. "d", occurrence - 1 + tonumber(digits))
      .. suffix
  end
  return result
end

local function resolve(source, payload, profile, uuids)
  if profile.kind == "icc" and not profile.icc_identity then
    return nil,
      reject(
        "color_profile",
        "Only the packaged linear-sRGB and Display P3 ICC identities are supported"
      )
  end
  if payload.format == "png" and source.colorMode == ColorMode.GRAY and profile.kind == "icc" then
    return nil,
      reject("color_profile", "Grayscale PNG does not support the admitted RGB ICC profiles")
  end
  local numbers, tag_index, tag_facts = payload.playback.frame_numbers, nil, nil
  if payload.playback.kind == "tag" then
    local tag, index, code, message = tags.resolve(source, payload.playback.tag)
    if not tag then return nil, reject(code, message) end
    tag_index = index
    tag_facts = inspection.inspect(source, { "tags" }).tags[index]
    numbers = {}
    local first, last = tag.fromFrame.frameNumber, tag.toFrame.frameNumber
    local reverse = tag.aniDir == AniDir.REVERSE or tag.aniDir == AniDir.PING_PONG_REVERSE
    local step = reverse and -1 or 1
    if reverse then
      first, last = last, first
    end
    for frame = first, last, step do
      numbers[#numbers + 1] = frame
    end
    if tag.aniDir == AniDir.PING_PONG or tag.aniDir == AniDir.PING_PONG_REVERSE then
      if math.abs(last - first) > 1 then
        for frame = last - step, first + step, -step do
          numbers[#numbers + 1] = frame
        end
      end
    end
  end
  local occurrences = {}
  for index, number in ipairs(numbers) do
    if number < 1 or number > #source.frames then
      return nil, reject("frame_number", "Source Frame Number exceeds timeline")
    end
    occurrences[index] = {
      occurrence = index,
      source_frame_number = number,
      source_duration_ms = math.floor(source.frames[number].duration * 1000 + 0.5),
    }
    if payload.format == "gif" and occurrences[index].source_duration_ms < 10 then
      return nil,
        reject(
          "gif_duration",
          "GIF requires each selected Source Frame duration to be at least 10 ms"
        )
    end
  end
  local limits = payload.operation_limits
  local pixels = source.width * source.height
  if
    #occurrences > limits.frame_occurrences
    or pixels > limits.canvas_pixels
    or pixels * #occurrences > limits.total_pixels
  then
    return nil,
      reject(
        "operation_limit",
        string.format(
          "Export allows at most %d Frame occurrences, %d Canvas pixels, and %d total pixels",
          limits.frame_occurrences,
          limits.canvas_pixels,
          limits.total_pixels
        )
      )
  end
  local context, failed = composition.resolve(source, payload.layer_composition, selection, uuids)
  if failed then return nil, reject("layer_composition", failed.rejection.message) end
  if context.direct_reference then
    return nil, reject("layer_composition", "Direct inclusion of a Reference Layer is unsupported")
  end
  local names = { "animation.gif" }
  if payload.format == "png" then
    local failure
    names, failure = filenames(payload.destination.filename_format, #occurrences)
    if failure then return nil, failure end
  end
  return {
    width = source.width,
    height = source.height,
    color_mode = source.colorMode == ColorMode.RGB and "rgb"
      or source.colorMode == ColorMode.GRAY and "grayscale"
      or "indexed",
    color_profile = profile.kind,
    icc_identity = profile.icc_identity or null,
    playback = {
      mode = tag_index and "tag_traversal" or "explicit_frames",
      tag_index = tag_index or null,
      tag = tag_facts or null,
      occurrences = occurrences,
    },
    filenames = names,
  }
end

function module.encode_png(image, path, palette, background, filename_format, occurrence)
  local temporary = Sprite(image.spec)
  local ok, result = pcall(function()
    if palette then temporary:setPalette(Palette(palette)) end
    app.activeSprite = temporary
    if background then app.command.BackgroundFromLayer { ui = false } end
    temporary.cels[1].image = image
    local prefix, digits, suffix = filename_format:match("^([^{}]*){frame(0*[01])}([^{}]*)$")
    -- The one-Frame container starts at ordinal zero. Let Aseprite's formatter
    -- apply the requested output-occurrence offset and padding to the actual file.
    local ordinal = string.format("%0" .. #digits .. "d", occurrence - 1 + tonumber(digits))
    app.command.SaveFileCopyAs {
      ui = false,
      filename = path,
      filenameFormat = app.fs.filePath(path)
        .. "/"
        .. prefix
        .. "{frame"
        .. ordinal
        .. "}"
        .. suffix,
      ignoreEmpty = false,
    }
  end)
  temporary:close()
  if not ok then error(result) end
end

local function write_bytes(path, bytes)
  local file = assert(io.open(path, "wb"))
  assert(file:write(bytes))
  assert(file:close())
end

function module.execute(payload)
  local source = nil
  local previous = { sprite = app.activeSprite, layer = app.activeLayer, frame = app.activeFrame }
  local ok, result = pcall(function()
    source = assert(app.open(payload.source_sprite_file), "could not open Source Sprite")
    local profile = profiles.restore_file_profile(source, payload.source_sprite_file)
    local uuids = inspection.saved_layer_uuids(source, payload.source_sprite_file)
    local resolution, failure = resolve(source, payload, profile, uuids)
    if failure then return failure end
    if payload.phase == "resolve" then return resolution end
    assert(payload.phase == "encode", "unknown export phase")
    if payload.format == "gif" then
      return {
        resolution = resolution,
        frames = gif.encode(
          source,
          resolution.playback.occurrences,
          payload.layer_composition,
          uuids,
          profile,
          payload.output_directory .. "/" .. payload.output_filename,
          payload.evidence_directory
        ),
      }
    end
    local frames = {}
    for index, occurrence in ipairs(resolution.playback.occurrences) do
      local image, paths, rejected, background = composition.render(
        source,
        occurrence.source_frame_number,
        payload.layer_composition,
        { x = 0, y = 0, width = source.width, height = source.height },
        selection,
        uuids,
        "preserve"
      )
      if rejected then return reject("layer_composition", rejected.rejection.message) end
      local palette, palette_frame = palettes.resolve(source, occurrence.source_frame_number)
      local palette_facts = null
      if source.colorMode == ColorMode.INDEXED then
        if not palette or #palette < 1 or #palette > 256 or source.transparentColor >= #palette then
          return reject(
            "palette",
            "Indexed PNG requires 1-256 complete Palette entries including its Transparent Color Index"
          )
        end
        local missing = composition.missing_output_index(image, palette)
        if missing then return reject("palette", missing.rejection.message) end
        local entries = {}
        for entry = 0, #palette - 1 do
          local c = palette:getColor(entry)
          entries[#entries + 1] = {
            index = entry,
            color = { red = c.red, green = c.green, blue = c.blue, alpha = c.alpha },
          }
        end
        palette_facts = {
          palette_frame_number = palette_frame,
          transparent_color_index = source.transparentColor,
          entries = entries,
        }
      end
      local filename = resolution.filenames[index]
      write_bytes(payload.evidence_directory .. "/" .. index .. ".pixels", image.bytes)
      module.encode_png(
        image,
        payload.output_directory .. "/" .. filename,
        palette,
        background,
        payload.destination.filename_format,
        index
      )
      frames[index] = {
        occurrence = index,
        source_frame_number = occurrence.source_frame_number,
        filename = filename,
        effective_background = background,
        resolved_layer_paths = paths,
        effective_palette = palette_facts,
      }
    end
    return { resolution = resolution, frames = frames }
  end)
  if source then pcall(function() source:close() end) end
  if previous.sprite and previous.sprite.isValid then
    pcall(function()
      app.activeSprite, app.activeLayer, app.activeFrame =
        previous.sprite, previous.layer, previous.frame
    end)
  end
  if not ok then error(result) end
  return result
end

function module.probe_sequence()
  local root = app.params.workspace .. "/sequence-probe"
  app.fs.makeDirectory(root)
  local source = root .. "/source.aseprite"
  local fixture = Sprite(2, 1, ColorMode.RGB)
  fixture.cels[1].image:putPixel(0, 0, app.pixelColor.rgba(80, 20, 40, 255))
  assert(fixture:saveAs(source))
  fixture:close()
  local result = module.execute {
    phase = "encode",
    format = "png",
    source_sprite_file = source,
    playback = { kind = "frames", frame_numbers = { 1, 1 } },
    layer_composition = { mode = "visible" },
    destination = { filename_format = "frame{frame1}.png" },
    output_directory = root,
    evidence_directory = root,
    operation_limits = { frame_occurrences = 2, canvas_pixels = 2, total_pixels = 4 },
  }
  assert(not result.rejection and #result.frames == 2, "native sequence did not complete")
  for _, frame in ipairs(result.frames) do
    local decoded = Sprite { fromFile = root .. "/" .. frame.filename, oneFrame = true }
    assert(decoded.width == 2 and decoded.height == 1 and #decoded.frames == 1)
    decoded:close()
  end
end

function module.probe_gif()
  local root = app.params.workspace .. "/gif-probe"
  app.fs.makeDirectory(root)
  local source = root .. "/source.aseprite"
  local fixture = Sprite(2, 1, ColorMode.RGB)
  fixture.cels[1].image:putPixel(0, 0, app.pixelColor.rgba(80, 20, 40, 128))
  assert(fixture:saveAs(source))
  fixture:close()
  local result = module.execute {
    phase = "encode",
    format = "gif",
    source_sprite_file = source,
    playback = { kind = "frames", frame_numbers = { 1, 1 } },
    layer_composition = { mode = "visible" },
    destination = {},
    output_directory = root,
    output_filename = "animation.gif",
    evidence_directory = root,
    operation_limits = { frame_occurrences = 2, canvas_pixels = 2, total_pixels = 4 },
  }
  assert(not result.rejection and #result.frames == 2, "native GIF did not complete")
  local file = assert(io.open(root .. "/animation.gif", "rb"))
  local signature = file:read(6)
  file:close()
  assert(signature == "GIF89a", "native GIF signature differs")
end

return module
