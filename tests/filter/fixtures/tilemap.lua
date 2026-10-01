local mode = app.params.mode == "indexed" and ColorMode.INDEXED or ColorMode.RGB
local sprite = Sprite(2, 1, mode)
local ordinary = sprite.layers[1]
ordinary.name = "Ordinary"
local palette = sprite.palettes[1]
palette:resize(3)
palette:setColor(0, Color { r = 0, g = 0, b = 0, a = 0 })
palette:setColor(1, Color { r = 80, g = 40, b = 20, a = 100 })
palette:setColor(2, Color { r = 120, g = 40, b = 20, a = 101 })
ordinary
  :cel(1).image
  :putPixel(0, 0, mode == ColorMode.INDEXED and 1 or app.pixelColor.rgba(80, 40, 20, 100))
sprite.gridBounds = Rectangle(0, 0, 1, 1)
app.command.NewLayer { tilemap = true, ui = false }
local layer = app.activeLayer
layer.name = "Tilemap"
for i = 1, 2 do
  local tile = sprite:newTile(layer.tileset)
  tile.image:putPixel(0, 0, mode == ColorMode.INDEXED and i or app.pixelColor.rgba(80, 40, 20, 100))
  tile.data = "keep-" .. i
end
local map = Image(2, 1, ColorMode.TILEMAP)
map:putPixel(0, 0, 1 | 0x80000000)
sprite:newCel(layer, 1, map, Point(0, 0))
if app.params.only == "true" then sprite:deleteLayer(ordinary) end
assert(sprite:saveAs(app.params.source))
sprite:close()
