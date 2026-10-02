if app.params.target then
  local sprite = assert(app.open(app.params.source))
  app.activeCel = sprite.cels[1]
  assert(app.site.tilesetMode == TilesetMode.MANUAL)
  app.range:clear()
  app.range.layers = { sprite.layers[1] }
  app.range.frames = { 1 }
  app.range.colors = {}
  local mask = Selection(Rectangle(0, 0, 2, 2))
  mask:subtract(Rectangle(1, 0, 1, 1))
  sprite.selection = mask
  assert(app.command.BrightnessContrast {
    ui = false,
    channels = FilterChannels.RED,
    brightness = 50,
    contrast = 0,
  })
  assert(sprite:saveAs(app.params.target))
  sprite:close()
  return
end

local sprite = Sprite(4, 4, ColorMode.RGB)
local ordinary = sprite.layers[1]
local width = tonumber(app.params.width or "2")
sprite.gridBounds = Rectangle(0, 0, width, 2)
app.command.NewLayer { tilemap = true, ui = false }
local layer = app.activeLayer
layer.name = "Spatial"
local tile = sprite:newTile(layer.tileset)
tile.data = "retain tile data"
tile.color = Color { r = 1, g = 2, b = 3, a = 4 }
tile.properties("other.plugin").nested = { point = Point(1, 2), text = "retain" }
for y = 0, 1 do
  for x = 0, width - 1 do
    tile.image:putPixel(x, y, app.pixelColor.rgba(40 + 20 * x + 10 * y, 20, 10, 160 + 10 * x))
  end
end
local unused = sprite:newTile(layer.tileset)
unused.image:clear(app.pixelColor.rgba(99, 88, 77, 255))
local map = Image(3, 2, ColorMode.TILEMAP)
local flags = math.tointeger(tonumber(app.params.flags))
map:putPixel(0, 0, 1 | flags)
map:putPixel(1, 1, 1 | flags)
-- Noncanonical flagged Empty placement is native-readable too.
map:putPixel(2, 1, 0x80000000)
local offset = tonumber(app.params.offset)
sprite:newCel(layer, 1, map, Point(offset, offset))
sprite:deleteLayer(ordinary)
assert(sprite:saveAs(app.params.source))
sprite:close()
