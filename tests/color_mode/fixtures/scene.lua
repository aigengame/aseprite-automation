-- Independent native fixture: linked and independent Cels, background, and tiles.
local mode = ({ rgb = ColorMode.RGB, grayscale = ColorMode.GRAY, indexed = ColorMode.INDEXED })[app.params.mode]
local sprite = Sprite(8, 8, mode)
local palette = Palette(6)
for index, rgba in ipairs {
  { 10, 20, 30, 255 },
  { 220, 40, 60, 255 },
  { 30, 200, 80, 128 },
  { 0, 0, 0, 0 },
  { 80, 90, 230, 255 },
  { 255, 255, 255, 255 },
} do
  palette:setColor(index - 1, Color { r = rgba[1], g = rgba[2], b = rgba[3], a = rgba[4] })
end
sprite:setPalette(palette)
sprite.transparentColor = 3
local ink = sprite.layers[1]
ink.name = "Ink"
local image = ink:cel(1).image
for y = 0, 7 do
  for x = 0, 7 do
    local pixel
    if mode == ColorMode.RGB then
      pixel = app.pixelColor.rgba(x * 31 + 10, y * 29 + 20, (x + y) * 15, x == 0 and 0 or x * 36)
    elseif mode == ColorMode.GRAY then
      pixel = app.pixelColor.graya((x + y) * 17, x == 0 and 0 or x * 36)
    else
      pixel = (x + y) % 6
    end
    image:drawPixel(x, y, pixel)
  end
end
ink:cel(1).opacity = 120
app.activeSprite, app.activeLayer, app.activeFrame = sprite, ink, sprite.frames[1]
app.command.NewFrame { content = "cellinked" }
assert(ink:cel(1).image == ink:cel(2).image)
sprite:newEmptyFrame(3)
sprite:newCel(ink, 3, Image(image), Point(0, 0))
local background = sprite:newLayer()
background.name = "Background"
app.activeLayer = background
app.bgColor = Color { r = 20, g = 30, b = 40, a = 255 }
app.command.BackgroundFromLayer()
assert(background.isBackground)
app.activeSprite, app.activeLayer = sprite, ink
app.command.NewLayer { tilemap = true, gridBounds = Rectangle(0, 0, 2, 2) }
local tilemap = app.activeLayer
tilemap.name = "Tiles"
assert(tilemap.isTilemap)
local tileset = tilemap.tileset
tileset.name = "Terrain"
local tile = sprite:newTile(tileset)
local pixels = Image(2, 2, mode)
pixels:drawPixel(0, 0, image:getPixel(3, 3))
pixels:drawPixel(1, 0, image:getPixel(5, 5))
pixels:drawPixel(0, 1, image:getPixel(2, 6))
pixels:drawPixel(1, 1, image:getPixel(6, 2))
tile.image = pixels
local map = Image(2, 2, ColorMode.TILEMAP)
map:clear(app.pixelColor.tile(tile.index))
sprite:newCel(tilemap, 1, map, Point(0, 0))
-- Include an unreferenced Tileset; complete-Sprite conversion still owns it.
local unused = sprite:newTileset(Rectangle(0, 0, 2, 2), 2)
unused.name = "Unused"
unused:tile(1).image = pixels
assert(sprite:saveAs(app.params.source))
sprite:close()
