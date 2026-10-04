-- One bounded Preparation invocation composes existing native Raster and Color owners.
local profiles = dofile(app.params.color_profile)
local palettes = dofile(app.params.palette)
local palette_transform = dofile(app.params.palette_transform)
local modes = dofile(app.params.color_mode)
local canvas = dofile(app.params.image_canvas_transform)
local resize = dofile(app.params.image_resize_transform)
local alpha = dofile(app.params.image_alpha)
local delivery = dofile(app.params.export_image_support)
local digest = dofile(app.params.digest)
local null = json.decode("null")
local source, working = nil, nil
local previous = {
  sprite = app.activeSprite,
  layer = app.activeLayer,
  frame = app.activeFrame,
  foreground = app.fgColor,
  background = app.bgColor,
  manage = app.preferences.color.manage,
  files_with_profile = app.preferences.color.files_with_profile,
  missing_profile = app.preferences.color.missing_profile,
}

local function require_fact(condition, reason, message)
  if not condition then
    error({ preparation_refusal = true, reason = reason, message = message })
  end
end

local function bytes(hex)
  assert(
    type(hex) == "string" and #hex % 2 == 0 and not hex:find("[^%x]"),
    "Invalid frozen byte encoding"
  )
  return (hex:gsub("%x%x", function(value) return string.char(tonumber(value, 16)) end))
end

local function write_file(path, content)
  local file = assert(io.open(path, "wb"))
  assert(file:write(content))
  assert(file:close())
end

local function size(value)
  return math.tointeger(value.width)
    and value.width >= 1
    and value.width <= 65535
    and math.tointeger(value.height)
    and value.height >= 1
    and value.height <= 65535
end

local function same_rectangle(left, right)
  return left ~= nil
    and right ~= nil
    and left.x == right.x
    and left.y == right.y
    and left.width == right.width
    and left.height == right.height
end

local function palette_entries(sprite)
  local result = {}
  for index = 0, #sprite.palettes[1] - 1 do
    local color = sprite.palettes[1]:getColor(index)
    result[#result + 1] = {
      red = color.red,
      green = color.green,
      blue = color.blue,
      alpha = color.alpha,
    }
  end
  return result
end

local function rgba_bytes(image, palette, mask)
  if image.colorMode == ColorMode.RGB then return image.bytes end
  local result = {}
  for pixel in image:pixels() do
    local index = pixel()
    require_fact(index >= 0 and index < #palette, "mapping", "Stored index is outside Palette")
    local color = palette:getColor(index)
    result[#result + 1] = index == mask and string.rep("\0", 4)
      or string.pack("BBBB", color.red, color.green, color.blue, color.alpha)
  end
  return table.concat(result)
end

local function execute()
  local file = assert(io.open(app.params.request, "rb"))
  local request = json.decode(file:read("a"))
  file:close()
  assert(request.kernel_protocol_version == 1, "Unsupported Kernel Protocol")
  local input = assert(request.payload)
  local spec, geometry, decoded = input.specification, input.geometry, input.decoded
  local frozen = bytes(input.raster_bytes)
  local private_png = app.params.workspace .. "/preparation-input.png"
  write_file(private_png, frozen)
  local check = assert(io.open(private_png, "rb"))
  local consumed = check:read("a")
  check:close()
  require_fact(consumed == frozen, "native_input", "Private PNG differs from frozen input")
  app.preferences.color.manage = true
  app.preferences.color.files_with_profile = 1
  app.preferences.color.missing_profile = 0
  local loaded, opened = pcall(app.open, private_png)
  if loaded then source = opened end
  require_fact(source ~= nil, "native_input", "Aseprite could not load the frozen PNG")
  require_fact(
    source.colorMode == ColorMode.RGB and #source.frames == 1 and #source.cels == 1,
    "native_input",
    "Native PNG structure differs from admitted input"
  )
  local image = source.cels[1].image
  require_fact(
    source.width == decoded.width
      and source.height == decoded.height
      and image.width == decoded.width
      and image.height == decoded.height
      and image.bytesPerPixel == 4
      and image.rowStride == image.width * 4,
    "native_input",
    "Native PNG dimensions or layout differ from decoded input"
  )
  local source_rgba = image.bytes
  require_fact(
    source_rgba == bytes(decoded.rgba_bytes),
    "native_input",
    "Native PNG pixels differ from independently decoded input"
  )
  local icc_bytes = type(decoded.icc_bytes) == "string" and bytes(decoded.icc_bytes) or nil
  local restored, state =
    pcall(profiles.restore_declared_profile, source, decoded.color_profile, icc_bytes)
  require_fact(restored, "color_profile", "Native PNG Color Profile differs from encoded input")
  local source_identity = state.icc_identity or null
  local operation = decoded.color_profile == "icc" and "convert" or "assign"
  local changed, profile = pcall(
    profiles.apply_live,
    source,
    operation,
    { profile = { kind = "srgb" } },
    {},
    state
  )
  require_fact(
    changed and not profile.rejection,
    "color_profile",
    changed and profile.rejection and profile.rejection.code
      or "Native profile normalization failed"
  )
  image = source.cels[1].image
  -- Compare literal alpha channels before thresholding; conversion owns RGB changes only.
  local source_alpha, normalized_alpha = {}, {}
  local normalized_rgba = image.bytes
  for offset = 4, #source_rgba, 4 do
    source_alpha[#source_alpha + 1] = source_rgba:sub(offset, offset)
    normalized_alpha[#normalized_alpha + 1] = normalized_rgba:sub(offset, offset)
  end
  require_fact(
    table.concat(source_alpha) == table.concat(normalized_alpha),
    "color_profile",
    "Native Color Profile conversion changed alpha"
  )
  require_fact(
    source.colorSpace == ColorSpace { sRGB = true },
    "color_profile",
    "Effective Color Profile is not sRGB"
  )
  local bounds
  image, bounds = alpha.normalize(image, spec.alpha_threshold)
  require_fact(
    size(geometry.resized) and size(geometry.canvas),
    "geometry",
    "Preparation dimensions exceed native bounds"
  )
  require_fact(
    canvas.contains_rectangle(image, geometry.crop),
    "geometry",
    "Crop Rectangle is outside source Image"
  )
  if spec.crop.kind == "rectangle" then
    require_fact(
      same_rectangle(spec.crop.rectangle, geometry.crop),
      "geometry",
      "Explicit crop differs from declared Rectangle"
    )
  else
    require_fact(spec.crop.kind == "automatic", "geometry", "Unsupported crop policy")
    require_fact(
      same_rectangle(bounds, geometry.crop),
      "geometry",
      "Automatic crop differs from thresholded nontransparent bounds"
    )
  end
  require_fact(
    geometry.canvas.width == spec.canvas.width and geometry.canvas.height == spec.canvas.height,
    "geometry",
    "Output canvas differs from specification"
  )
  if spec.resize.kind == "size" then
    require_fact(
      geometry.resized.width == spec.resize.width and geometry.resized.height == spec.resize.height,
      "geometry",
      "Exact resize dimensions differ from specification"
    )
  end
  image = canvas.crop(image, geometry.crop)
  image = resize.resize(
    image,
    source,
    geometry.resized.width,
    geometry.resized.height,
    "nearest-neighbor",
    nil
  )
  -- A disposable regular Layer makes mapping and encoding independent of source Background behavior.
  working = Sprite(ImageSpec(image.spec))
  working.cels[1].image = image
  local requested = spec.palette.entries
  local count = #requested
  local mask = spec.palette.transparent_index
  require_fact(
    count >= 2 and count <= 256 and math.tointeger(mask) and mask >= 0 and mask < count,
    "mapping",
    "Palette size or transparent index is outside admitted bounds"
  )
  for index, color in ipairs(requested) do
    require_fact(
      (
        index - 1 == mask
        and color.red == 0
        and color.green == 0
        and color.blue == 0
        and color.alpha == 0
      ) or (index - 1 ~= mask and color.alpha == 255),
      "mapping",
      "Palette must have one canonical transparent entry and otherwise opaque colors"
    )
  end
  require_fact(spec.mapping.dithering == "none", "mapping", "Preparation requires no dithering")
  local growth = {}
  for index = #working.palettes[1], count - 1 do
    growth[#growth + 1] = { index = index, color = requested[index + 1] }
  end
  local resized_palette = palette_transform.resize(
    working,
    { palette_frame_number = 1, size = count, entries = growth },
    {}
  )
  require_fact(not resized_palette.rejection, "mapping", "Native Palette sizing failed")
  local edits = {}
  for index, color in ipairs(requested) do
    edits[#edits + 1] = { index = index - 1, color = color }
  end
  local installed = palettes.set(working, { palette_frame_number = 1, entries = edits }, {})
  require_fact(not installed.rejection, "mapping", "Native Palette installation failed")
  local converted = modes.change(working, {
    source_color_mode = "rgb",
    target = {
      color_mode = "indexed",
      rgb_map_algorithm = spec.mapping.rgb_map_algorithm,
      color_best_fit_criteria = spec.mapping.color_best_fit_criteria,
      dithering = { algorithm = "none" },
    },
  })
  require_fact(
    not converted.rejection and working.transparentColor == spec.palette.transparent_index,
    "mapping",
    "Native mapping differs from declared transparent index"
  )
  local offset = geometry.offset
  require_fact(
    math.tointeger(offset.x)
      and math.tointeger(offset.y)
      and offset.x >= 0
      and offset.y >= 0
      and offset.x + geometry.resized.width <= geometry.canvas.width
      and offset.y + geometry.resized.height <= geometry.canvas.height,
    "geometry",
    "Resized Image rectangle falls outside output canvas"
  )
  image = canvas.canvas_resize(
    working.cels[1].image,
    geometry.canvas.width,
    geometry.canvas.height,
    offset,
    { kind = "palette-index", index = spec.palette.transparent_index }
  )
  working.cels[1].image = image
  local output_palette = palette_entries(working)
  if spec.output_mode == "rgba" then
    local rgb =
      modes.change(working, { source_color_mode = "indexed", target = { color_mode = "rgb" } })
    require_fact(not rgb.rejection, "mapping", "Native RGB output conversion failed")
    image = working.cels[1].image
  else
    require_fact(spec.output_mode == "indexed", "mapping", "Unsupported output Color Mode")
  end
  local tagged_spec = ImageSpec(image.spec)
  tagged_spec.colorSpace = ColorSpace { sRGB = true }
  local tagged = Image(tagged_spec)
  tagged.bytes = image.bytes
  local rgba = rgba_bytes(tagged, working.palettes[1], spec.palette.transparent_index)
  write_file(input.staged_rgba_file, rgba)
  delivery.encode_image(
    tagged,
    input.staged_png_file,
    spec.output_mode == "indexed" and working.palettes[1] or nil
  )
  local alpha_min, alpha_max = 255, 0
  for byte_offset = 4, #rgba, 4 do
    local value = rgba:byte(byte_offset)
    alpha_min, alpha_max = math.min(alpha_min, value), math.max(alpha_max, value)
  end
  return {
    width = tagged.width,
    height = tagged.height,
    color_profile = "srgb",
    alpha_min = alpha_min,
    alpha_max = alpha_max,
    rendered_byte_size = #rgba,
    source_rgba_digest = digest.fnv1a64(source_rgba),
    normalized_rgba_digest = digest.fnv1a64(normalized_rgba),
    normalized_alpha_preserved = true,
    profile = {
      source_kind = decoded.color_profile,
      source_icc_identity = source_identity,
      assumption = decoded.color_profile == "none" and "srgb" or null,
      effective = "srgb",
      converted = operation == "convert",
    },
    crop = {
      x = geometry.crop.x,
      y = geometry.crop.y,
      width = geometry.crop.width,
      height = geometry.crop.height,
    },
    resized = { width = geometry.resized.width, height = geometry.resized.height },
    offset = { x = geometry.offset.x, y = geometry.offset.y },
    mapping = converted.mapping,
    dithering = converted.dithering,
    palette_entries = output_palette,
    transparent_index = spec.palette.transparent_index,
    output_mode = spec.output_mode,
    stored_content_digest = digest.fnv1a64(tagged.bytes),
    rgba_content_digest = digest.fnv1a64(rgba),
  }
end

local ok, result = pcall(execute)
if working ~= nil then pcall(function() working:close() end) end
if source ~= nil then pcall(function() source:close() end) end
if previous.sprite ~= nil and previous.sprite.isValid then
  pcall(function() app.activeSprite = previous.sprite end)
  pcall(function() app.activeLayer = previous.layer end)
  pcall(function() app.activeFrame = previous.frame end)
end
pcall(function() app.fgColor = previous.foreground end)
pcall(function() app.bgColor = previous.background end)
pcall(function() app.preferences.color.manage = previous.manage end)
pcall(function() app.preferences.color.files_with_profile = previous.files_with_profile end)
pcall(function() app.preferences.color.missing_profile = previous.missing_profile end)
local response
if ok then
  response = { kernel_protocol_version = 1, status = "ok", result = result }
elseif type(result) == "table" and result.preparation_refusal then
  response = {
    kernel_protocol_version = 1,
    status = "ok",
    result = {
      rejection = {
        code = "preparation_rejected",
        details = { reason = result.reason, message = result.message },
      },
    },
  }
else
  response = {
    kernel_protocol_version = 1,
    status = "error",
    cause = "operation_rejected",
    message = tostring(result),
  }
end
write_file(app.params.response, json.encode(response))
