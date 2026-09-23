-- Native fixtures for Paint target semantics that Sprite create does not yet expose.
local kind = assert(app.params.kind)
local target = assert(app.params.out)
local sprite

if kind == "linked-rgb" then
  sprite = Sprite(4, 3, ColorMode.RGB)
  local layer = sprite.layers[1]
  local image = Image(2, 2, ColorMode.RGB)
  image:clear(app.pixelColor.rgba(0, 0, 0, 0))
  local first = assert(layer:cel(1))
  first.image = image
  first.position = Point(1, 0)
  layer.isContinuous = true
  sprite:newFrame(1)
  layer.isContinuous = false
  local third_frame = sprite:newEmptyFrame()
  sprite:newCel(layer, third_frame, Image(first.image), Point(1, 0))
elseif kind == "grayscale" then
  sprite = Sprite(2, 2, ColorMode.GRAY)
elseif kind == "indexed" then
  sprite = Sprite(2, 2, ColorMode.INDEXED)
  local palette = Palette(2)
  palette:setColor(0, Color { r = 0, g = 0, b = 0, a = 0 })
  palette:setColor(1, Color { r = 241, g = 82, b = 65, a = 255 })
  sprite:setPalette(palette)
elseif kind == "indexed-background" then
  local alpha = tonumber(app.params.palette_alpha or "255")
  assert(alpha == 0 or alpha == 128 or alpha == 255)
  sprite = Sprite(2, 2, ColorMode.INDEXED)
  local palette = Palette(2)
  palette:setColor(0, Color { r = 0, g = 0, b = 0, a = alpha })
  palette:setColor(1, Color { r = 241, g = 82, b = 65, a = 255 })
  sprite:setPalette(palette)
  local layer = sprite.layers[1]
  local image = assert(layer:cel(1)).image
  for y = 0, 1 do
    for x = 0, 1 do
      image:putPixel(x, y, 1)
    end
  end
  app.activeSprite = sprite
  app.activeLayer = layer
  app.bgColor = Color(1)
  app.command.BackgroundFromLayer()
  assert(sprite.layers[1].isBackground)
elseif kind == "indexed-palette-change" then
  sprite = Sprite(2, 2, ColorMode.INDEXED)
  local layer = sprite.layers[1]
  local palette = Palette(2)
  palette:setColor(0, Color { r = 0, g = 0, b = 0, a = 0 })
  palette:setColor(1, Color { r = 241, g = 82, b = 65, a = 255 })
  sprite:setPalette(palette)
  layer.isContinuous = true
  sprite:newFrame(1)
  layer.isContinuous = false
  sprite:newEmptyFrame(2)
elseif kind == "group" then
  sprite = Sprite(2, 2, ColorMode.RGB)
  local image_layer = sprite.layers[1]
  sprite:newGroup()
  sprite:deleteLayer(image_layer)
elseif kind == "reference" then
  sprite = Sprite(2, 2, ColorMode.RGB)
  app.activeSprite = sprite
  app.activeLayer = sprite.layers[1]
  app.command.NewLayer { reference = true }
elseif kind == "tilemap" then
  sprite = Sprite(2, 2, ColorMode.RGB)
  local image_layer = sprite.layers[1]
  app.activeSprite = sprite
  app.activeLayer = image_layer
  app.command.NewLayer { tilemap = true }
  sprite:deleteLayer(image_layer)
elseif kind == "absent" then
  sprite = Sprite(2, 2, ColorMode.RGB)
  sprite:newEmptyFrame()
elseif kind == "large-rgb" then
  sprite = Sprite(2048, 2048, ColorMode.RGB)
elseif kind == "limit-rgb" then
  sprite = Sprite(257, 1, ColorMode.RGB)
else
  error("unknown Paint fixture kind")
end

assert(sprite:saveAs(target), "could not save Paint fixture")
sprite:close()
