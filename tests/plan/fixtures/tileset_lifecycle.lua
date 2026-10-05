-- Two shared references and a differently ordered keyed replacement.
local sprite = Sprite(12, 12, ColorMode.RGB)
app.activeSprite = sprite
app.command.NewLayer { tilemap = true, ask = false, gridBounds = Rectangle(0, 0, 2, 3) }
local map, old = app.activeLayer, app.activeLayer.tileset
map.name, old.name, old.baseIndex = "map", "terrain", 37
for _, key in ipairs({ "a", "b" }) do
  local tile = sprite:newTile(old)
  tile.properties("aigengame.spa").tile_key = key
  tile.image:clear(app.pixelColor.rgba(10, 20, 30, 255))
end
local image = Image(3, 1, ColorMode.TILEMAP)
image:putPixel(0, 0, 1 | 0xe0000000)
image:putPixel(1, 0, 2 | 0x80000000)
image:putPixel(2, 0, 0)
sprite:newCel(map, 1, image, Point(-2, 4))
app.command.NewFrame { content = "empty" }
app.command.NewLayer { tilemap = true, ask = false, gridBounds = Rectangle(0, 0, 2, 3) }
local peer, generated = app.activeLayer, app.activeLayer.tileset
peer.name, peer.tileset = "peer", old
sprite:deleteTileset(generated)
sprite:newCel(peer, 1, Image(image), Point(3, -4))
local replacement = sprite:newTileset(Grid { x = 0, y = 0, width = 2, height = 3 }, 1)
replacement.name, replacement.baseIndex = "replacement", 81
for _, key in ipairs({ "b", "a" }) do
  local tile = sprite:newTile(replacement)
  tile.properties("aigengame.spa").tile_key = key
  tile.image:clear(app.pixelColor.rgba(40, 50, 60, 255))
end
assert(sprite:saveAs(app.params.source))
sprite:close()
