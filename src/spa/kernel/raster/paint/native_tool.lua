-- Private native Paint invocation. The caller owns clipping, Selection Application,
-- and the final write into the original shared Image.
local module = {}
local masks = dofile(app.params.selection_mask)

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
  eraser = true,
  paint_bucket = true,
  rectangle = true,
  filled_rectangle = true,
  ellipse = true,
  filled_ellipse = true,
  contour = true,
  blur = true,
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
  if tool == "paint_bucket" then
    return { checked_point(payload.seed.x + position.x, payload.seed.y + position.y) }
  end
  if tool == "pencil" or tool == "eraser" or tool == "contour" or tool == "blur" then
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

local function translate_points(points, offset)
  local translated = {}
  for _, point in ipairs(points) do
    translated[#translated + 1] = checked_point(point.x - offset.x, point.y - offset.y)
  end
  return translated
end

local function invoke(options)
  local cel, fill = options.cel, options.fill
  local sprite = cel.sprite
  app.activeSprite = sprite
  app.activeLayer = cel.layer
  app.activeFrame = cel.frame
  app.useTool {
    tool = options.tool,
    cel = cel,
    layer = cel.layer,
    frame = cel.frame,
    color = options.color,
    bgColor = options.background or options.color,
    brush = options.brush,
    ink = options.ink,
    opacity = options.opacity,
    button = options.button or MouseButton.LEFT,
    points = options.points,
    contiguous = fill == nil or fill.contiguous,
    tolerance = fill and fill.tolerance or 0,
    freehandAlgorithm = options.algorithm,
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
  local ink
  if tool == "blur" then
    ink = Ink.SIMPLE
  elseif tool ~= "eraser" then
    ink = assert(ink_types[payload.ink], "unsupported Paint Ink")
  end
  local opacity = checked_integer(payload.opacity, "Paint opacity")
  assert(opacity >= 0 and opacity <= 255, "Paint opacity is outside native range")
  local filling = tool == "paint_bucket"
  local brush = filling and Brush { type = BrushType.CIRCLE, size = 1, angle = 0 }
    or make_brush(payload.brush)
  local color, background, button
  if tool == "eraser" then
    local behavior = payload.behavior
    color = behavior.foreground_color
        and make_tool_color(behavior.foreground_color, sprite.colorMode)
      or Color { r = 0, g = 0, b = 0, a = 255 }
    background = behavior.background_color
        and make_tool_color(behavior.background_color, sprite.colorMode)
      or color
    button = behavior.kind == "replace-foreground-with-background" and MouseButton.RIGHT
      or MouseButton.LEFT
  elseif tool == "blur" then
    -- Blur's effect Ink ignores Tool Color; its public request has no Color.
    color = Color { r = 0, g = 0, b = 0, a = 255 }
  else
    color = make_tool_color(payload.color, sprite.colorMode)
  end
  local tiled = tool == "blur"
      and assert(({ none = 0, x = 1, y = 2, both = 3 })[payload.tiled_mode], "invalid Tiled Mode")
    or 0
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
  local crop = (filling or tool == "blur") and checked_rectangle(0, 0, sprite.width, sprite.height)
    or checked_rectangle(left, top, right - left, bottom - top)
  -- Tiled Blur coverage wraps within the original Sprite Canvas. Untiled
  -- coverage retains the complete Brush extent for Image-bounds preflight.
  local footprint_crop = (filling or tiled ~= 0) and crop
    or checked_rectangle(left, top, right - left, bottom - top)
  if filling then
    local seed = points[1]
    assert(
      seed.x >= 0 and seed.y >= 0 and seed.x < sprite.width and seed.y < sprite.height,
      "Fill seed is outside the Sprite Canvas"
    )
  end
  local native_points = translate_points(points, crop)
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
  -- A separate opaque Pencil pass measures Blur's brush coverage even when
  -- the native Blur effect changes no pixel.
  local mask_tool = (tool == "blur" or tool == "eraser") and "pencil" or tool
  local mask_pref = app.preferences.tool(mask_tool)
  local mask_filled, mask_preview, mask_corner =
    mask_pref.filled, mask_pref.filled_preview, mask_pref.corner_radius
  local fill_preferences = {}
  if filling then
    for _, name in ipairs { "paint_bucket", "magic_wand" } do
      local flood = app.preferences.tool(name).floodfill
      fill_preferences[#fill_preferences + 1] = {
        target = flood,
        refer_to = flood.refer_to,
        stop_at_grid = flood.stop_at_grid,
        pixel_connectivity = flood.pixel_connectivity,
      }
    end
  end
  local clone, mask_sprite
  local ok, answer = pcall(function()
    -- The native two-point controller must not pick up optional fill or
    -- rounded-corner preferences. Batch mode resets tool prefs once per tool;
    -- setting these values after app.preferences.tool() works in both modes.
    pref.filled = false
    pref.filled_preview = false
    pref.corner_radius = 0
    mask_pref.filled, mask_pref.filled_preview, mask_pref.corner_radius = false, false, 0
    app.preferences.symmetry_mode.enabled = false

    for _, entry in ipairs(fill_preferences) do
      entry.target.refer_to = payload.refer_to == "all-layers" and 1 or 0
      entry.target.stop_at_grid = payload.stop_at_grid and 2 or 0
      entry.target.pixel_connectivity = payload.connectivity == "eight-connected" and 1 or 0
    end
    local footprint
    if not filling then
      mask_sprite = Sprite(footprint_crop.width, footprint_crop.height, ColorMode.RGB)
      assert(
        mask_sprite.width == footprint_crop.width and mask_sprite.height == footprint_crop.height,
        "native Paint footprint canvas changed the requested extent"
      )
      local mask_cel = assert(mask_sprite.layers[1]:cel(1))
      local mask_doc = app.preferences.document(mask_sprite)
      mask_doc.grid.snap = false
      mask_doc.tiled.mode = tiled
      mask_doc.symmetry.mode = 0
      local white = Color { r = 255, g = 255, b = 255, a = 255 }
      invoke {
        tool = mask_tool,
        cel = mask_cel,
        brush = brush,
        color = white,
        ink = Ink.SIMPLE,
        opacity = 255,
        points = translate_points(points, footprint_crop),
        algorithm = algorithm,
      }
      mask_cel = mask_sprite.layers[1]:cel(1)
      footprint = footprint_from(mask_cel, footprint_crop, source_position)
    end

    clone = Sprite(sprite)
    clone.selection = Selection()
    clone.gridBounds = sprite.gridBounds
    if not filling and tool ~= "blur" then clone:crop(crop) end
    assert(
      clone.width == crop.width and clone.height == crop.height,
      "native Paint working canvas changed the requested extent"
    )
    local clone_cel = assert(resolve_layer(clone.layers, path):cel(frame_number))
    local clone_pref = app.preferences.document(clone)
    clone_pref.grid.snap = false
    clone_pref.tiled.mode = tiled
    clone_pref.symmetry.mode = 0
    if filling then
      -- Both native tools use the same floodfill point shape. Observe matching
      -- before painting, including no-op colors and opacity, then clear the mask.
      invoke {
        tool = "magic_wand",
        cel = clone_cel,
        brush = brush,
        color = color,
        ink = Ink.SIMPLE,
        opacity = 255,
        points = native_points,
        algorithm = 0,
        fill = payload,
      }
      footprint =
        masks.translate(masks.copy(clone.selection), -source_position.x, -source_position.y)
      clone.selection = Selection()
    end
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
    if tool == "eraser" then app.bgColor = background end
    invoke {
      tool = tool,
      cel = clone_cel,
      brush = brush,
      color = color,
      ink = ink,
      opacity = opacity,
      points = native_points,
      algorithm = algorithm,
      background = background,
      button = button,
      fill = filling and payload or nil,
    }
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
    local result = { image = output, footprint = footprint }
    if filling then
      result.source_scope = {
        kind = payload.refer_to,
        frame_number = frame_number,
        canvas_bounds = { x = 0, y = 0, width = sprite.width, height = sprite.height },
      }
      if payload.stop_at_grid then
        local grid, seed = sprite.gridBounds, points[1]
        assert(grid.width > 0 and grid.height > 0, "Fill requires a valid saved Grid")
        result.effective_grid_cell = {
          x = grid.x + math.floor((seed.x - grid.x) / grid.width) * grid.width,
          y = grid.y + math.floor((seed.y - grid.y) / grid.height) * grid.height,
          width = grid.width,
          height = grid.height,
        }
      end
    end
    return result
  end)

  if clone ~= nil and clone.isValid then pcall(function() clone:close() end) end
  if mask_sprite ~= nil and mask_sprite.isValid then pcall(function() mask_sprite:close() end) end
  local restored, restore_error = pcall(function()
    mask_pref.filled, mask_pref.filled_preview, mask_pref.corner_radius =
      mask_filled, mask_preview, mask_corner
    for _, entry in ipairs(fill_preferences) do
      entry.target.refer_to = entry.refer_to
      entry.target.stop_at_grid = entry.stop_at_grid
      entry.target.pixel_connectivity = entry.pixel_connectivity
    end
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
