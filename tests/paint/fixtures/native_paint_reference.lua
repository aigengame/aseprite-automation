-- Independent native fixture and editor-tool reference, without SPA Kernel helpers.
local file = assert(io.open(app.params.input, "rb"))
local input = json.decode(file:read("*a"))
file:close()
local mode = ({ rgb = ColorMode.RGB, grayscale = ColorMode.GRAY, indexed = ColorMode.INDEXED })[input.mode]
local sprite = Sprite(8, 6, mode)
local layer = sprite.layers[1]
local image = layer:cel(1).image
local blue = mode == ColorMode.RGB and app.pixelColor.rgba(0, 0, 255, 255)
  or mode == ColorMode.GRAY and app.pixelColor.graya(40, 255)
  or 1
if mode == ColorMode.INDEXED then
  local palette = Palette(8)
  for index = 0, 7 do
    palette:setColor(index, Color { r = 0, g = 255, b = 0, a = 255 })
  end
  palette:setColor(1, Color { r = 0, g = 0, b = 255, a = 255 })
  palette:setColor(2, Color { r = 255, g = 0, b = 0, a = 255 })
  palette:setColor(3, Color { r = 128, g = 0, b = 127, a = 255 })
  palette:setColor(7, Color { r = 0, g = 0, b = 0, a = 0 })
  sprite:setPalette(palette)
  sprite.transparentColor = 7
end
image:clear(blue)
if input.pattern then
  for y = 0, image.height - 1 do
    for x = 0, image.width - 1 do
      local value = mode == ColorMode.RGB
          and app.pixelColor.rgba(
            (x * x * 29 + y * 17) % 256,
            (x * 61 + y * y * 23) % 256,
            (x * y * 47) % 256,
            255
          )
        or mode == ColorMode.GRAY and app.pixelColor.graya((x * x * 29 + y * y * 17) % 256, 255)
        or (x + y) % 4
      image:putPixel(x, y, value)
    end
  end
end
if input.hidden then
  image:putPixel(
    7,
    5,
    mode == ColorMode.RGB and app.pixelColor.rgba(17, 31, 49, 0)
      or mode == ColorMode.GRAY and app.pixelColor.graya(49, 0)
      or 7
  )
end
if input.background then
  app.activeSprite, app.activeLayer = sprite, layer
  app.bgColor = mode == ColorMode.RGB and Color { r = 0, g = 0, b = 255 }
    or mode == ColorMode.GRAY and Color { gray = 40 }
    or Color { index = 1 }
  app.command.BackgroundFromLayer()
end
if input.offset then layer:cel(1).position = Point(-2, 3) end
if input.linked then
  layer.isContinuous = true
  sprite:newFrame(1)
  layer.isContinuous = false
  sprite:newEmptyFrame()
  sprite:newCel(layer, 3, Image(image), layer:cel(1).position)
end
if input.source_sprite_file then
  sprite:close()
  sprite = assert(app.open(input.source_sprite_file))
  layer = sprite.layers[1]
end
if input.target_kind == "absent" then
  sprite:newEmptyFrame()
elseif input.target_kind == "group" then
  local group = sprite:newGroup()
  sprite:deleteLayer(layer)
  layer = group
elseif input.target_kind == "reference" or input.target_kind == "tilemap" then
  app.activeSprite, app.activeLayer = sprite, layer
  app.command.NewLayer {
    reference = input.target_kind == "reference",
    tilemap = input.target_kind == "tilemap",
  }
  sprite:deleteLayer(layer)
end
assert(sprite:saveAs(app.params.source))
if app.params.reference then
  local frame_number = input.frame_number or 1
  local cel = layer:cel(frame_number)
  local original_image, original_position = Image(cel.image), cel.position
  local first, last
  if input.points then
    first, last = input.points[1], input.points[#input.points]
  elseif input.tool == "line" then
    first, last = input["from"], input.to
  else
    local b = input.bounds
    first = { x = b.x, y = b.y }
    last = { x = b.x + b.width - 1, y = b.y + b.height - 1 }
  end
  local color = mode == ColorMode.RGB and Color { r = 255, g = 0, b = 0, a = 255 }
    or mode == ColorMode.GRAY and Color { gray = 200, alpha = 255 }
    or Color { index = 2 }
  local brush = Brush {
    type = ({ circle = BrushType.CIRCLE, square = BrushType.SQUARE, line = BrushType.LINE })[input.brush.kind],
    size = input.brush.size,
    angle = input.brush.angle or 0,
  }
  app.preferences.tool(input.tool).filled = false
  app.preferences.tool(input.tool).corner_radius = 0
  app.preferences.document(sprite).tiled.mode = ({ none = 0, x = 1, y = 2, both = 3 })[input.tiled_mode or "none"]
  local points = {}
  for _, point in ipairs(input.points or { first, last }) do
    points[#points + 1] = Point(point.x + cel.position.x, point.y + cel.position.y)
  end
  app.useTool {
    tool = input.tool,
    cel = cel,
    layer = layer,
    frame = sprite.frames[frame_number],
    color = color,
    bgColor = color,
    brush = brush,
    ink = ({
      simple = Ink.SIMPLE,
      ["alpha-compositing"] = Ink.ALPHA_COMPOSITING,
      ["copy-color"] = Ink.COPY_COLOR,
      ["lock-alpha"] = Ink.LOCK_ALPHA,
    })[input.ink],
    opacity = input.opacity,
    button = MouseButton.LEFT,
    points = points,
    freehandAlgorithm = input.freehand_algorithm == "pixel-perfect" and 1 or 0,
  }
  if input.preserve_geometry then
    local native = layer:cel(frame_number)
    for y = 0, original_image.height - 1 do
      for x = 0, original_image.width - 1 do
        local cx, cy = x + original_position.x, y + original_position.y
        local in_canvas = cx >= 0 and cy >= 0 and cx < sprite.width and cy < sprite.height
        if native and (input.tiled_mode == "none" or in_canvas) then
          local nx, ny = cx - native.position.x, cy - native.position.y
          if nx >= 0 and ny >= 0 and nx < native.image.width and ny < native.image.height then
            original_image:putPixel(x, y, native.image:getPixel(nx, ny))
          end
        end
      end
    end
    assert(native).image = original_image
    native.position = original_position
  end
  assert(sprite:saveAs(app.params.reference))
end
sprite:close()
