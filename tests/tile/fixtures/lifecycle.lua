-- Shared, linked, and orphan Tile records with opaque native metadata.
local mode = ({ rgb = ColorMode.RGB, grayscale = ColorMode.GRAY, indexed = ColorMode.INDEXED })[app.params.mode or "rgb"]
local sprite = Sprite(16, 16, mode)
sprite.transparentColor = mode == ColorMode.INDEXED and 7 or 0
app.activeSprite = sprite
app.command.NewLayer { tilemap = true, ask = false, gridBounds = Rectangle(0, 0, 2, 3) }
local layer, tileset = app.activeLayer, app.activeLayer.tileset
layer.name, tileset.name, tileset.baseIndex =
  "map", "terrain", tonumber(app.params.base_index or "37")
for index, key in ipairs({ "a", "b", "c", "d" }) do
  local tile = sprite:newTile(tileset)
  tile.image:clear(mode == ColorMode.RGB and app.pixelColor.rgba(10 + index, 30, 40, 255) or index)
  tile.data = "data-" .. index
  tile.color = Color { r = 20 + index, g = 30, b = 40, a = 255 }
  tile.properties.note = "default-" .. index
  tile.properties("example").large = 9007199254740993 + index
  tile.properties("example").point = Point(index, -index)
  tile.properties("example").binary = string.char(255, 254, index)
  tile.properties("aigengame.spa").other = "retained-" .. index
  if app.params.unkeyed ~= tostring(index) then
    tile.properties("aigengame.spa").tile_key = app.params.duplicate == tostring(index) and "a"
      or key
  end
end
local image = Image(5, 1, ColorMode.TILEMAP)
for x = 0, 3 do
  image:putPixel(x, 0, (x + 1) | 0xe0000000)
end
image:putPixel(4, 0, 0xe0000000)
if app.params.unused then image:putPixel(tonumber(app.params.unused) - 1, 0, 0) end
if app.params.invalid then image:putPixel(0, 0, 99 | 0x80000000) end
sprite:newCel(layer, 1, image, Point(-3, 7))
app.activeLayer = layer
app.command.NewFrame { content = "cellinked" }
assert(layer:cel(1).image == layer:cel(2).image)
app.command.NewLayer { tilemap = true, ask = false, gridBounds = Rectangle(0, 0, 2, 3) }
local peer, generated = app.activeLayer, app.activeLayer.tileset
peer.name, peer.tileset = "peer", tileset
sprite:deleteTileset(generated)
sprite:newCel(peer, 2, Image(image), Point(4, -2))
local group = sprite:newGroup()
group.name = "nested"
peer.parent = group
local orphan = sprite:newTileset(Grid { x = 0, y = 0, width = 2, height = 3 }, 1)
orphan.name = "orphan"
for index, key in ipairs({ "x", "y" }) do
  local tile = sprite:newTile(orphan)
  tile.properties("aigengame.spa").tile_key = key
  tile.properties("example").binary = string.char(255, 254, index)
end
assert(sprite:saveAs(app.params.source))
sprite:close()
