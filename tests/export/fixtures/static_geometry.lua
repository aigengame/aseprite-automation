-- Native Sources for bounded static export geometry and composition cases.
local variant = app.params.variant or "geometry"
local sprite
if variant == "geometry" or variant == "ambiguous_layer" then
  sprite = Sprite(5, 3, ColorMode.RGB)
  local layer = sprite.layers[1]
  layer.name = "pattern"
  for frame = 1, 4 do
    if frame > 1 then
      sprite:newEmptyFrame()
      sprite:newCel(layer, frame, Image(5, 3, ColorMode.RGB))
    end
    local image = layer:cel(frame).image
    for y = 0, 2 do
      for x = 0, 4 do
        image:drawPixel(x, y, app.pixelColor.rgba(10 + x * 20, 30 + y * 40, frame * 50, 255))
      end
    end
  end
  if variant == "ambiguous_layer" then
    local duplicate = sprite:newLayer()
    duplicate.name = "pattern"
    sprite:newCel(duplicate, 1, Image(5, 3, ColorMode.RGB))
  end
elseif variant == "indexed" or variant == "indexed_background" then
  sprite = Sprite(3, 1, ColorMode.INDEXED)
  local palette = Palette(8)
  for index = 0, 7 do
    palette:setColor(index, Color { r = index * 10, g = index * 11, b = index * 12, a = 255 })
  end
  palette:setColor(1, Color { r = 200, g = 0, b = 0, a = 255 })
  palette:setColor(2, Color { r = 0, g = 0, b = 200, a = 128 })
  palette:setColor(3, palette:getColor(1))
  sprite:setPalette(palette)
  sprite.transparentColor = 7
  local base = sprite.layers[1]
  base.name = "base"
  base:cel(1).image.bytes = string.char(1, 7, 7)
  if variant == "indexed_background" then
    app.activeSprite, app.activeLayer = sprite, base
    app.bgColor = Color { index = 7 }
    app.command.BackgroundFromLayer { ui = false }
    assert(base.isBackground)
  end
  local top = sprite:newLayer()
  top.name = "overlay"
  local image = Image(3, 1, ColorMode.INDEXED)
  image.bytes = string.char(2, 7, 1)
  sprite:newCel(top, 1, image)
elseif variant == "mixed_tilemap" then
  sprite = Sprite(4, 1, ColorMode.RGB)
  local ordinary = sprite.layers[1]
  ordinary.name = "ordinary"
  ordinary:cel(1).image:drawPixel(3, 0, app.pixelColor.rgba(200, 30, 40, 255))
  sprite.gridBounds = Rectangle(0, 0, 1, 1)
  app.activeSprite = sprite
  app.command.NewLayer { tilemap = true, ui = false }
  local tiles = app.activeLayer
  tiles.name = "tiles"
  app.useTool {
    tool = "pencil",
    layer = tiles,
    color = Color { r = 11, g = 22, b = 33, a = 255 },
    tilesetMode = TilesetMode.STACK,
    points = { Point(1, 0) },
  }
else
  error("unknown fixture variant")
end
assert(sprite:saveAs(app.params.out))
sprite:close()
