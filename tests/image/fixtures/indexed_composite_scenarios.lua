-- Native Indexed fixtures for preserve-composite behavior and Palette boundaries.
local mode = assert(app.params.mode)
local mask = (mode == "plain-255" or mode == "missing-mask") and 255 or 7
local sprite = Sprite(3, 1, ColorMode.INDEXED)
local palette =
  Palette((mode == "missing-mask" or mode == "short-earlier-palette") and 4 or mask + 1)
palette:setColor(0, Color { r = 30, g = 40, b = 50, a = 255 })
palette:setColor(3, Color { r = 250, g = 0, b = 0, a = 255 })
if mask < #palette then palette:setColor(mask, Color { r = 0, g = 0, b = 250, a = 255 }) end
sprite:setPalette(palette)
sprite.transparentColor = mask
local layer = sprite.layers[1]
layer.name = "Ink"
local image = layer:cel(1).image
image:clear(mask)
image:putPixel(0, 0, 0)
image:putPixel(2, 0, 3)
if mode == "hidden-group" then
  local outer = sprite:newGroup()
  outer.name = "Outer"
  outer.opacity = 128
  outer.blendMode = BlendMode.MULTIPLY
  local inner = sprite:newGroup()
  inner.name = "Inner"
  inner.parent = outer
  inner.opacity = 192
  layer.parent = inner
  outer.isVisible, inner.isVisible, layer.isVisible = false, false, false
elseif mode == "linked-frames" or mode == "short-earlier-palette" then
  app.activeSprite, app.activeLayer, app.activeFrame = sprite, layer, sprite.frames[1]
  app.command.NewFrame { content = "cellinked" }
  assert(sprite.cels[1].image.id == sprite.cels[2].image.id)
elseif mode == "background-visible" or mode == "background-hidden" then
  app.activeSprite, app.activeLayer = sprite, layer
  app.command.BackgroundFromLayer()
  local background = sprite.layers[1]
  local pixels = background:cel(1).image
  pixels:putPixel(0, 0, 0)
  pixels:putPixel(1, 0, mask)
  pixels:putPixel(2, 0, 3)
  background.isVisible = mode == "background-visible"
elseif mode == "tilemap" then
  sprite.gridBounds = Rectangle(0, 0, 1, 1)
  app.activeSprite, app.activeLayer = sprite, layer
  app.command.NewLayer { tilemap = true }
  local tiles = app.activeLayer
  tiles.name = "Tiles"
  app.useTool {
    tool = "pencil",
    color = Color { index = 1 },
    layer = tiles,
    tilesetMode = TilesetMode.STACK,
    points = { Point(0, 0) },
  }
  app.useTool {
    tool = "pencil",
    color = Color { index = 3 },
    layer = tiles,
    tilesetMode = TilesetMode.STACK,
    points = { Point(2, 0) },
  }
  sprite:deleteLayer(layer)
  -- The native NewLayer path allocates Tile 0 before the nonzero mask is settled.
  sprite.transparentColor = 2
  sprite.transparentColor = mask
  local first_tile = app.pixelColor.tileI(sprite.cels[1].image:getPixel(0, 0))
  assert(first_tile ~= 0)
  sprite.tilesets[1]:tile(first_tile).image:putPixel(0, 0, 0)
  local rgb_spec = sprite.spec
  rgb_spec.colorMode, rgb_spec.transparentColor = ColorMode.RGB, 0
  local rgb = Image(rgb_spec)
  rgb:drawSprite(sprite, 1)
  assert(app.pixelColor.rgbaR(rgb:getPixel(0, 0)) == 30)
  assert(app.pixelColor.rgbaA(rgb:getPixel(1, 0)) == 0)
  assert(app.pixelColor.rgbaR(rgb:getPixel(2, 0)) == 250)
end
assert(sprite:saveAs(app.params.out))
sprite:close()
