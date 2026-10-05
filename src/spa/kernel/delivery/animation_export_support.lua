-- Asset Delivery owns playback and encoding; rendering/profile semantics use their owners.
local module = {}
local composition = dofile(app.params.layer_composition)
local selection = dofile(app.params.layer_select)
local inspection = dofile(app.params.inspection)
local profiles = dofile(app.params.color_profile)
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
  if source.colorMode ~= ColorMode.RGB or profile.kind == "icc" then
    return nil, reject("representation", "This PNG sequence path requires RGB with None or sRGB")
  end
  local occurrences = {}
  for index, number in ipairs(payload.playback.frame_numbers) do
    if number < 1 or number > #source.frames then
      return nil, reject("frame_number", "Source Frame Number exceeds timeline")
    end
    occurrences[index] = {
      occurrence = index,
      source_frame_number = number,
      source_duration_ms = math.floor(source.frames[number].duration * 1000 + 0.5),
    }
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
  local names, failure = filenames(payload.destination.filename_format, #occurrences)
  if failure then return nil, failure end
  return {
    width = source.width,
    height = source.height,
    color_mode = "rgb",
    color_profile = profile.kind,
    icc_identity = profile.icc_identity or null,
    playback = { mode = "explicit_frames", occurrences = occurrences },
    filenames = names,
  }
end

function module.encode_png(image, path, palette, background)
  local temporary = Sprite(image.spec)
  local ok, result = pcall(function()
    if palette then temporary:setPalette(Palette(palette)) end
    app.activeSprite = temporary
    if background then app.command.BackgroundFromLayer { ui = false } end
    temporary.cels[1].image = image
    app.command.SaveFileCopyAs {
      ui = false,
      filename = path,
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
      local filename = resolution.filenames[index]
      write_bytes(payload.evidence_directory .. "/" .. index .. ".pixels", image.bytes)
      module.encode_png(image, payload.output_directory .. "/" .. filename, nil, background)
      frames[index] = {
        occurrence = index,
        source_frame_number = occurrence.source_frame_number,
        filename = filename,
        effective_background = background,
        resolved_layer_paths = paths,
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

return module
