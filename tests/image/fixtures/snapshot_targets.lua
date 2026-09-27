app.preferences.experimental.compose_groups = true
local mode = app.params.mode or "rgb"
local color_mode = mode:find("grayscale", 1, true) == 1 and ColorMode.GRAY
  or mode:find("indexed", 1, true) == 1 and ColorMode.INDEXED
  or ColorMode.RGB
local sprite = Sprite(mode == "large" and 65 or 4, mode == "large" and 65 or 3, color_mode)
local layer = sprite.layers[1]
layer.name = "Stored"
local image = layer:cel(1).image
if color_mode == ColorMode.RGB then
  image:clear(app.pixelColor.rgba(10, 20, 30, 255))
  image:putPixel(1, 1, app.pixelColor.rgba(70, 80, 90, 0))
  image:putPixel(2, 1, app.pixelColor.rgba(3, 4, 5, 128))
elseif color_mode == ColorMode.GRAY then
  image:clear(app.pixelColor.graya(42, 255))
  image:putPixel(1, 1, app.pixelColor.graya(72, 0))
  image:putPixel(2, 1, app.pixelColor.graya(9, 128))
else
  local palette = Palette(4)
  palette:setColor(0, Color { r = 30, g = 40, b = 50, a = 255 })
  palette:setColor(1, Color { r = 250, g = 0, b = 0, a = 255 })
  palette:setColor(2, Color { r = 0, g = 0, b = 250, a = 255 })
  palette:setColor(
    3,
    Color { r = 0, g = 250, b = 0, a = mode == "indexed-background-alpha" and 128 or 255 }
  )
  sprite:setPalette(palette)
  sprite.transparentColor = mode == "indexed-zero-composite" and 0 or 2
  image:clear(1)
  image:putPixel(1, 1, 0)
  image:putPixel(2, 1, 2)
end
layer.isVisible = false
layer:cel(1).opacity = 0
if mode:find("composite", 1, true) then
  layer.isVisible = true
  layer:cel(1).opacity = 255
elseif mode == "indexed-blend" or mode == "indexed-opacity" then
  layer.isVisible, layer:cel(1).opacity = true, 255
  local palette = sprite.palettes[1]
  palette:setColor(0, Color { r = 200, g = 100, b = 50, a = 255 })
  palette:setColor(1, Color { r = 100, g = 200, b = 100, a = 255 })
  palette:setColor(3, Color { r = 60, g = 120, b = 240, a = 128 })
  image:clear(1)
  local group = sprite:newGroup()
  local child = sprite:newLayer()
  child.parent = group
  local pixels = Image(sprite.spec)
  pixels:clear(2)
  pixels:putPixel(1, 1, 0)
  pixels:putPixel(3, 1, 3)
  sprite:newCel(child, 1, pixels)
elseif mode == "blend" or mode == "default-group" then
  layer.isVisible = true
  layer:cel(1).opacity = 255
  image:clear(app.pixelColor.rgba(200, 100, 50, 255))
  local group = sprite:newGroup()
  local top = sprite:newLayer()
  top.parent = group
  local tint = Image(4, 3, ColorMode.RGB)
  tint:clear(app.pixelColor.rgba(128, 200, 255, 255))
  sprite:newCel(top, 1, tint)
elseif mode == "tilemap" or mode == "indexed-tilemap" then
  sprite.gridBounds = Rectangle(0, 0, 1, 1)
  app.activeSprite, app.activeLayer = sprite, layer
  app.command.NewLayer { tilemap = true }
  local tiles = app.activeLayer
  app.useTool {
    tool = "pencil",
    color = color_mode == ColorMode.INDEXED and Color { index = 1 }
      or app.pixelColor.rgba(250, 0, 0, 255),
    layer = tiles,
    tilesetMode = TilesetMode.STACK,
    points = { Point(1, 1) },
  }
  sprite:deleteLayer(layer)
elseif mode == "reference" then
  app.activeSprite = sprite
  app.command.NewLayer { reference = true, ui = false }
  local reference = app.activeLayer
  sprite:newCel(reference, 1, Image(image), Point(0, 0))
  sprite:deleteLayer(layer)
elseif mode:find("background", 1, true) then
  layer.isVisible = true
  layer:cel(1).opacity = 255
  image:clear(
    color_mode == ColorMode.RGB and app.pixelColor.rgba(40, 60, 80, 255)
      or color_mode == ColorMode.GRAY and app.pixelColor.graya(40, 255)
      or 1
  )
  app.activeSprite = sprite
  app.activeLayer = layer
  app.command.BackgroundFromLayer()
elseif mode == "absent" then
  sprite:newEmptyFrame()
elseif mode == "duplicate" then
  local second = sprite:newLayer()
  second.name = layer.name
elseif mode == "linked" or mode == "indexed-linked" or mode == "indexed-palette" then
  if mode == "indexed-palette" then
    layer.isVisible, layer:cel(1).opacity = true, 255
  end
  app.activeSprite = sprite
  app.activeLayer = layer
  app.activeFrame = sprite.frames[1]
  app.command.NewFrame { content = "cellinked" }
elseif mode == "composition" then
  local outside = sprite:newLayer()
  outside.name = "Outside"
  local blue = Image(1, 1, ColorMode.RGB)
  blue:clear(app.pixelColor.rgba(0, 0, 255, 255))
  sprite:newCel(outside, 1, blue, Point(1, 1))
  local group = sprite:newGroup()
  group.name = "Character"
  group.opacity = 128
  group.isVisible = false
  local nested = sprite:newGroup()
  nested.name = "Nested"
  nested.parent = group
  nested.isVisible = false
  local ink = sprite:newLayer()
  ink.name = "Ink"
  ink.parent = nested
  ink.isVisible = false
  local red = Image(1, 1, ColorMode.RGB)
  red:clear(app.pixelColor.rgba(255, 0, 0, 255))
  sprite:newCel(ink, 1, red, Point(1, 1)).opacity = 128
  local green = sprite:newLayer()
  green.name = "Other"
  green.parent = group
  local patch = Image(1, 1, ColorMode.RGB)
  patch:clear(app.pixelColor.rgba(0, 255, 0, 255))
  sprite:newCel(green, 1, patch, Point(2, 1))
end
assert(sprite:saveAs(app.params.out))
sprite:close()
