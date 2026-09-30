-- Color and Palette owns native conversion on an attached Sprite, without publication.
local module = {}
local palettes = dofile(app.params.palette)
local effective = dofile(app.params.effective_palette)
local layers = dofile(app.params.layer_select)
local digest = dofile(app.params.digest)
local null = json.decode("null")
local modes =
  { [ColorMode.RGB] = "rgb", [ColorMode.GRAY] = "grayscale", [ColorMode.INDEXED] = "indexed" }
local formats = { rgb = "rgb", grayscale = "gray", indexed = "indexed" }

function module.observe(sprite)
  local images, cels, tilesets, seen = {}, {}, {}, {}
  local function image_facts(image, kind, frame)
    if seen[image.id] then return seen[image.id] end
    local number = #images + 1
    seen[image.id] = number
    local palette_frame = null
    if frame then
      local _palette, change = effective.resolve(sprite, frame)
      palette_frame = change
    end
    local indexes = null
    if image.colorMode == ColorMode.INDEXED then
      local counts = {}
      for pixel in image:pixels() do
        local value = pixel()
        counts[value] = (counts[value] or 0) + 1
      end
      indexes = {}
      for index, count in pairs(counts) do
        indexes[#indexes + 1] = { index = index, pixel_count = count }
      end
      table.sort(indexes, function(a, b) return a.index < b.index end)
    end
    images[number] = {
      image_number = number,
      kind = kind,
      width = image.width,
      height = image.height,
      bytes_per_pixel = image.bytesPerPixel,
      row_stride = image.rowStride,
      content = digest.fnv1a64(image.bytes),
      conversion_frame_number = frame or null,
      palette_frame_number = palette_frame,
      palette_indices = indexes,
    }
    return number
  end
  for _, cel in ipairs(sprite.cels) do
    local tilemap = cel.layer.isTilemap
    cels[#cels + 1] = {
      layer_path = layers.current_path(sprite, cel.layer),
      frame_number = cel.frame.frameNumber,
      image_number = image_facts(
        cel.image,
        tilemap and "tilemap" or "cel",
        not tilemap and cel.frame.frameNumber or nil
      ),
      opacity = cel.opacity,
      is_background = cel.layer.isBackground,
    }
  end
  for number, tileset in ipairs(sprite.tilesets) do
    local tiles = {}
    for index = 0, #tileset - 1 do
      tiles[#tiles + 1] = {
        tile_index = index,
        image_number = tileset:tile(index).image
            and image_facts(tileset:tile(index).image, "tile", 1)
          or null,
      }
    end
    tilesets[#tilesets + 1] = { tileset_number = number, name = tileset.name, tiles = tiles }
  end
  return {
    color_mode = assert(modes[sprite.colorMode]),
    transparent_color_index = sprite.transparentColor,
    palettes = palettes.list(sprite),
    images = images,
    cels = cels,
    tilesets = tilesets,
  }
end

local function rejection(code, message, details)
  return { rejection = { code = code, message = message, details = details } }
end

local function object(value) return type(value) == "table" or type(value) == "userdata" end

local function installed_matrices(id)
  -- Invocation isolates the user configuration. Installed IDs address the selected
  -- installation's data/extensions; conversion uses the uniquely resolved file.
  local root = app.fs.joinPath(assert(app.params.aseprite_data), "extensions")
  local matches = {}
  if not app.fs.isDirectory(root) then return matches end
  for _, name in ipairs(app.fs.listFiles(root)) do
    local directory = app.fs.joinPath(root, name)
    local file = io.open(app.fs.joinPath(directory, "package.json"), "rb")
    if file then
      local bytes = file:read("*a")
      file:close()
      local ok, package = pcall(json.decode, bytes)
      if
        ok
        and object(package)
        and object(package.contributes)
        and object(package.contributes.ditheringMatrices)
      then
        for _, entry in ipairs(package.contributes.ditheringMatrices) do
          if
            object(entry)
            and entry.id == id
            and type(entry.path) == "string"
            and entry.path ~= ""
          then
            matches[#matches + 1] = app.fs.joinPath(directory, entry.path)
          end
        end
      end
    end
  end
  table.sort(matches)
  return matches
end

local function resolve_matrix(requested)
  if not requested then
    return {
      provenance = "native-default",
      requested = null,
      resolved_path = null,
      identity = "bayer8x8",
      width = 8,
      height = 8,
    },
      nil
  end
  requested = requested.kind == "installed" and { kind = "installed", id = requested.id }
    or { kind = "file", path = requested.path }
  local matches = requested.kind == "installed" and installed_matrices(requested.id)
    or { requested.path }
  local function fail(reason)
    return nil,
      nil,
      rejection(
        "dithering_matrix_invalid",
        "Dithering Matrix " .. reason,
        { matrix = requested, reason = reason, matches = matches }
      )
  end
  if #matches == 0 then return fail("missing") end
  if #matches > 1 then return fail("ambiguous") end
  local path = matches[1]
  if path:sub(1, 1) ~= "/" then path = app.fs.joinPath(app.fs.currentPath, path) end
  path = app.fs.normalizePath(path)
  if not app.fs.isFile(path) then return fail("missing") end
  local file = io.open(path, "rb")
  if not file then return fail("unreadable") end
  local bytes = file:read("*a")
  file:close()
  if not bytes then return fail("unreadable") end
  -- Snapshot the requested bytes. Validation and conversion read this one private
  -- file, so a changing external file cannot turn native loading into a fallback.
  local staged =
    app.fs.joinPath(assert(app.params.workspace), "dithering-matrix." .. app.fs.fileExtension(path))
  local copy = assert(io.open(staged, "wb"), "could not stage Dithering Matrix")
  assert(copy:write(bytes), "could not stage Dithering Matrix bytes")
  copy:close()
  local matrix = nil
  local previous = { sprite = app.activeSprite, layer = app.activeLayer, frame = app.activeFrame }
  local ok, dimensions = pcall(function()
    matrix = assert(app.open(staged), "native Matrix load failed")
    local first = assert(matrix.layers[1], "Matrix has no first Layer")
    local cel = assert(first:cel(1), "Matrix has no first Frame Cel")
    assert(
      cel.image.width == matrix.width and cel.image.height == matrix.height,
      "Matrix Image does not cover its native dimensions"
    )
    return { width = matrix.width, height = matrix.height }
  end)
  if matrix then pcall(function() matrix:close() end) end
  if previous.sprite and previous.sprite.isValid then
    app.activeSprite = previous.sprite
    app.activeLayer = previous.layer
    app.activeFrame = previous.frame
  end
  if not ok then return fail("invalid") end
  return {
    provenance = requested.kind,
    requested = requested,
    resolved_path = path,
    identity = requested.kind == "installed" and requested.id or digest.fnv1a64(bytes),
    width = dimensions.width,
    height = dimensions.height,
  },
    staged
end

local function change(sprite, conversion)
  local before = module.observe(sprite)
  if before.color_mode ~= conversion.source_color_mode then
    return rejection(
      "color_mode_mismatch",
      "Source Color Mode differs from requested branch",
      { expected = conversion.source_color_mode, actual = before.color_mode }
    )
  end
  local target = conversion.target
  local changed = before.color_mode ~= target.color_mode
  local mapping, dithering = null, null
  local command = { ui = false, format = formats[target.color_mode], toGray = target.to_gray }
  if changed and target.color_mode == "indexed" then
    command.rgbmap = target.rgb_map_algorithm
    command.fitCriteria = target.color_best_fit_criteria
    -- Native Sprite::rgbMap resolves DEFAULT to Octree on the verified baseline.
    mapping = {
      requested_rgb_map_algorithm = target.rgb_map_algorithm,
      effective_rgb_map_algorithm = target.rgb_map_algorithm == "default" and "octree"
        or target.rgb_map_algorithm,
      color_best_fit_criteria = target.color_best_fit_criteria,
    }
    if target.dithering then
      command.dithering = target.dithering.algorithm
      command.ditheringFactor = target.dithering.dithering_factor
      local matrix, path, failed = nil, nil, nil
      if command.dithering == "ordered" or command.dithering == "old" then
        matrix, path, failed = resolve_matrix(target.dithering.matrix)
        if failed then return failed end
        command.ditheringMatrix = path
      end
      dithering = {
        requested_algorithm = target.dithering.algorithm,
        effective_algorithm = target.dithering.algorithm,
        matrix = matrix or null,
        dithering_factor = target.dithering.dithering_factor or null,
        effective_factor_percent = target.dithering.dithering_factor and math.floor(
          target.dithering.dithering_factor * 100
        ) or null,
      }
    end
  end
  if changed then
    app.activeSprite = sprite
    app.command.ChangePixelFormat(command)
    assert(
      modes[sprite.colorMode] == target.color_mode,
      "Native conversion did not change Color Mode"
    )
  end
  return {
    source_color_mode = before.color_mode,
    target_color_mode = target.color_mode,
    changed = changed,
    to_gray = target.to_gray or null,
    mapping = mapping,
    dithering = dithering,
    before = before,
    after = module.observe(sprite),
  }
end

function module.change(sprite, conversion)
  local previous = {
    sprite = app.activeSprite,
    layer = app.activeLayer,
    frame = app.activeFrame,
    foreground = app.fgColor,
    background = app.bgColor,
  }
  local ok, result = pcall(change, sprite, conversion)
  if previous.sprite and previous.sprite.isValid then
    pcall(function() app.activeSprite = previous.sprite end)
    pcall(function() app.activeLayer = previous.layer end)
    pcall(function() app.activeFrame = previous.frame end)
  end
  pcall(function() app.fgColor = previous.foreground end)
  pcall(function() app.bgColor = previous.background end)
  if not ok then error(result, 0) end
  return result
end

return module
