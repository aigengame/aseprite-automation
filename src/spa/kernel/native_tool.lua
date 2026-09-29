-- Private native Paint invocation. The caller owns clipping, Selection Application,
-- and the final write into the original shared Image.
local module = {}

local brush_types = {
  circle = BrushType.CIRCLE,
  square = BrushType.SQUARE,
  line = BrushType.LINE,
}

local ink_types = {
  simple = Ink.SIMPLE,
  ["alpha-compositing"] = Ink.ALPHA_COMPOSITING,
  ["copy-color"] = Ink.COPY_COLOR,
  ["lock-alpha"] = Ink.LOCK_ALPHA,
}

local allowed_tools = {
  line = true,
  pencil = true,
  rectangle = true,
  filled_rectangle = true,
  ellipse = true,
  filled_ellipse = true,
}

local function checked_integer(value, label)
  assert(type(value) == "number" and value % 1 == 0, "invalid " .. label)
  return value
end

local function checked_point(x, y)
  checked_integer(x, "native x")
  checked_integer(y, "native y")
  local point = Point(x, y)
  assert(point.x == x and point.y == y, "Paint Point is not representable natively")
  return point
end

local function checked_rectangle(x, y, width, height)
  checked_integer(width, "native width")
  checked_integer(height, "native height")
  assert(width > 0 and height > 0, "invalid native Paint bounds")
  local rectangle = Rectangle(x, y, width, height)
  assert(
    rectangle.x == x
      and rectangle.y == y
      and rectangle.width == width
      and rectangle.height == height,
    "Paint bounds are not representable natively"
  )
  checked_point(x + width, y + height)
  return rectangle
end

local function make_brush(value)
  assert(type(value) == "table" or type(value) == "userdata", "missing Standard Paint Brush")
  local kind = assert(brush_types[value.kind], "unsupported Standard Paint Brush")
  local size = checked_integer(value.size, "Brush size")
  assert(size > 0, "Brush size must be positive")
  local angle = value.kind == "circle" and 0 or checked_integer(value.angle, "Brush angle")
  assert(angle >= -180 and angle <= 180, "Brush angle is outside native range")
  if value.kind == "circle" then assert(value.angle == nil, "Circle Brush has no angle") end
  local brush = Brush { type = kind, size = size, angle = angle }
  assert(
    brush.type == kind and brush.size == size and brush.angle == angle,
    "native Brush changed the requested size or angle"
  )
  return brush
end

-- Color Value policy is validated by raster_color in the calling Paint module.
-- This adapter constructs Tool Color userdata, rather than packed Image pixels.
local function make_tool_color(value, mode)
  assert(type(value) == "table" or type(value) == "userdata", "missing Color Value")
  if mode == ColorMode.RGB then
    assert(value.kind == "rgba", "RGB target requires rgba Color Value")
    return Color { r = value.red, g = value.green, b = value.blue, a = value.alpha }
  elseif mode == ColorMode.GRAY then
    assert(value.kind == "grayscale", "Grayscale target requires grayscale Color Value")
    return Color { gray = value.gray, alpha = value.alpha }
  elseif mode == ColorMode.INDEXED then
    assert(value.kind == "palette-index", "Indexed target requires palette-index Color Value")
    return Color { index = value.index }
  end
  error("unsupported Color Mode")
end

local function find_layer_path(layers, target, prefix)
  for index, layer in ipairs(layers) do
    local path = {}
    for _, part in ipairs(prefix) do
      path[#path + 1] = part
    end
    path[#path + 1] = index
    if layer == target then return path end
    if layer.isGroup then
      local nested = find_layer_path(layer.layers, target, path)
      if nested then return nested end
    end
  end
  return nil
end

local function resolve_layer(layers, path)
  local layer
  for _, part in ipairs(path) do
    layer = assert(layers[part], "temporary target Layer disappeared")
    layers = layer.layers
  end
  return layer
end

local function geometry(payload, tool, position)
  if tool == "pencil" then
    assert(#payload.points > 0, "a gesture needs at least one Point")
    local points = {}
    for _, point in ipairs(payload.points) do
      points[#points + 1] = checked_point(point.x + position.x, point.y + position.y)
    end
    return points
  end
  local first, last
  if tool == "line" then
    local from = assert(payload["from"], "missing Line from Point")
    local to = assert(payload.to, "missing Line to Point")
    first = checked_point(from.x + position.x, from.y + position.y)
    last = checked_point(to.x + position.x, to.y + position.y)
  else
    local bounds = assert(payload.bounds, "missing Paint Shape bounds")
    assert(bounds.width > 0 and bounds.height > 0, "Paint Shape bounds must be positive")
    first = checked_point(bounds.x + position.x, bounds.y + position.y)
    last = checked_point(
      bounds.x + bounds.width - 1 + position.x,
      bounds.y + bounds.height - 1 + position.y
    )
  end
  return { first, last }
end

local function invoke(tool, cel, brush, color, ink, opacity, points, algorithm)
  local sprite = cel.sprite
  app.activeSprite = sprite
  app.activeLayer = cel.layer
  app.activeFrame = cel.frame
  app.useTool {
    tool = tool,
    cel = cel,
    layer = cel.layer,
    frame = cel.frame,
    color = color,
    bgColor = color,
    brush = brush,
    ink = ink,
    opacity = opacity,
    button = MouseButton.LEFT,
    points = points,
    contiguous = true,
    tolerance = 0,
    freehandAlgorithm = algorithm,
    selection = SelectionMode.REPLACE,
    tilemapMode = TilemapMode.PIXELS,
    tilesetMode = TilesetMode.MANUAL,
  }
end

local function pixel_at(cel, canvas_x, canvas_y)
  if cel == nil then return nil end
  local image = cel.image
  local x = canvas_x - cel.position.x
  local y = canvas_y - cel.position.y
  if x >= 0 and y >= 0 and x < image.width and y < image.height then return image:getPixel(x, y) end
  return nil
end

local function footprint_from(cel, crop, original_position)
  if cel == nil then return Selection() end
  local image = cel.image
  local offset = cel.position
  local result = Selection()
  for y = 0, image.height - 1 do
    local start = nil
    for x = 0, image.width do
      local present = x < image.width and app.pixelColor.rgbaA(image:getPixel(x, y)) ~= 0
      if present and start == nil then start = x end
      if not present and start ~= nil then
        local image_x = offset.x + start + crop.x - original_position.x
        local image_y = offset.y + y + crop.y - original_position.y
        result:add(checked_rectangle(image_x, image_y, x - start, 1))
        start = nil
      end
    end
  end
  return result
end

-- Returns native pixels for exactly the original Image extent and the complete
-- native tool footprint, including pixels outside that extent. No original
-- Sprite/Cel/Image is mutated.
function module.render(sprite, cel, payload, tool)
  assert(allowed_tools[tool], "unsupported native Paint tool")
  assert(cel ~= nil and cel.sprite == sprite, "invalid Paint target Cel")
  assert(
    cel.layer.isImage and not cel.layer.isTilemap and not cel.layer.isReference,
    "Paint target is not a regular Image Cel"
  )
  assert(type(payload) == "table" or type(payload) == "userdata", "missing native Paint payload")
  local ink = assert(ink_types[payload.ink], "unsupported Paint Ink")
  local opacity = checked_integer(payload.opacity, "Paint opacity")
  assert(opacity >= 0 and opacity <= 255, "Paint opacity is outside native range")
  local brush = make_brush(payload.brush)
  local color = make_tool_color(payload.color, sprite.colorMode)
  local source_image = cel.image
  local source_position = cel.position
  local points = geometry(payload, tool, source_position)
  local algorithm = ({ regular = 0, ["pixel-perfect"] = 1, dots = 2 })[payload.freehand_algorithm or "regular"]
  assert(algorithm ~= nil, "unsupported Freehand Algorithm")
  local margin = brush.size * 2 + 2
  local left, top = math.min(0, source_position.x), math.min(0, source_position.y)
  local right = math.max(sprite.width, source_position.x + source_image.width)
  local bottom = math.max(sprite.height, source_position.y + source_image.height)
  for _, point in ipairs(points) do
    left, top = math.min(left, point.x), math.min(top, point.y)
    right, bottom = math.max(right, point.x + 1), math.max(bottom, point.y + 1)
  end
  left, top, right, bottom = left - margin, top - margin, right + margin, bottom + margin
  local crop = checked_rectangle(left, top, right - left, bottom - top)
  local native_points = {}
  for _, point in ipairs(points) do
    native_points[#native_points + 1] = checked_point(point.x - crop.x, point.y - crop.y)
  end
  local path = assert(find_layer_path(sprite.layers, cel.layer, {}), "target Layer not in Sprite")
  local frame_number = cel.frame.frameNumber

  local previous = {
    sprite = app.activeSprite,
    layer = app.activeLayer,
    frame = app.activeFrame,
    tool = app.tool,
    brush = app.brush,
    fg = app.fgColor,
    bg = app.bgColor,
    symmetry = app.preferences.symmetry_mode.enabled,
  }
  local pref = app.preferences.tool(tool)
  -- Capture only the tool preferences this invocation changes.
  local pref_values = {
    filled = pref.filled,
    filled_preview = pref.filled_preview,
    corner_radius = pref.corner_radius,
  }
  local clone, mask_sprite
  local ok, answer = pcall(function()
    -- The native two-point controller must not pick up optional fill or
    -- rounded-corner preferences. Batch mode resets tool prefs once per tool;
    -- setting these values after app.preferences.tool() works in both modes.
    pref.filled = false
    pref.filled_preview = false
    pref.corner_radius = 0
    app.preferences.symmetry_mode.enabled = false

    mask_sprite = Sprite(crop.width, crop.height, ColorMode.RGB)
    assert(
      mask_sprite.width == crop.width and mask_sprite.height == crop.height,
      "native Paint footprint canvas changed the requested extent"
    )
    local mask_cel = assert(mask_sprite.layers[1]:cel(1))
    local mask_pref = app.preferences.document(mask_sprite)
    mask_pref.grid.snap = false
    mask_pref.tiled.mode = 0
    mask_pref.symmetry.mode = 0
    local white = Color { r = 255, g = 255, b = 255, a = 255 }
    invoke(tool, mask_cel, brush, white, Ink.SIMPLE, 255, native_points, algorithm)
    mask_cel = mask_sprite.layers[1]:cel(1)
    local footprint = footprint_from(mask_cel, crop, source_position)

    clone = Sprite(sprite)
    clone.selection = Selection()
    clone:crop(crop)
    assert(
      clone.width == crop.width and clone.height == crop.height,
      "native Paint working canvas changed the requested extent"
    )
    local clone_cel = assert(resolve_layer(clone.layers, path):cel(frame_number))
    local clone_pref = app.preferences.document(clone)
    clone_pref.grid.snap = false
    clone_pref.tiled.mode = 0
    clone_pref.symmetry.mode = 0
    local output = Image(source_image)
    for y = 0, source_image.height - 1 do
      for x = 0, source_image.width - 1 do
        local before =
          pixel_at(clone_cel, x + source_position.x - crop.x, y + source_position.y - crop.y)
        assert(
          before == source_image:getPixel(x, y),
          "temporary Sprite crop changed source Image pixels"
        )
      end
    end
    invoke(tool, clone_cel, brush, color, ink, opacity, native_points, algorithm)
    clone_cel = resolve_layer(clone.layers, path):cel(frame_number)
    local transparent = sprite.colorMode == ColorMode.INDEXED and sprite.transparentColor or 0
    for y = 0, source_image.height - 1 do
      for x = 0, source_image.width - 1 do
        local native =
          pixel_at(clone_cel, x + source_position.x - crop.x, y + source_position.y - crop.y)
        local requested = footprint:contains(Point(x, y))
        if native == nil and requested then native = transparent end
        if native ~= nil and requested then output:putPixel(x, y, native) end
      end
    end
    return { image = output, footprint = footprint }
  end)

  if clone ~= nil and clone.isValid then pcall(function() clone:close() end) end
  if mask_sprite ~= nil and mask_sprite.isValid then pcall(function() mask_sprite:close() end) end
  local restored, restore_error = pcall(function()
    pref.filled = pref_values.filled
    pref.filled_preview = pref_values.filled_preview
    pref.corner_radius = pref_values.corner_radius
    app.preferences.symmetry_mode.enabled = previous.symmetry
    if previous.sprite ~= nil and previous.sprite.isValid then
      app.activeSprite = previous.sprite
      app.activeLayer = previous.layer
      app.activeFrame = previous.frame
    end
    app.tool = previous.tool
    app.brush = previous.brush
    app.fgColor = previous.fg
    app.bgColor = previous.bg
  end)
  if not restored then
    error("native Paint state restoration failed: " .. tostring(restore_error))
  end
  if not ok then error(answer) end
  return answer
end

return module
