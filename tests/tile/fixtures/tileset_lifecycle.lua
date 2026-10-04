-- Two shared source Layers and a keyed destination with a different Tile order.
local indexed = app.params.mode == "indexed"
local sprite = Sprite(16, 16, indexed and ColorMode.INDEXED or ColorMode.RGB)
sprite.transparentColor = indexed and tonumber(app.params.transparent or "0") or 0
app.activeSprite = sprite
app.command.NewLayer { tilemap = true, ask = false, gridBounds = Rectangle(0, 0, 2, 3) }
local map, source = app.activeLayer, app.activeLayer.tileset
map.name, source.name, source.baseIndex = "map", "source", 11
for index, key in ipairs({ "a", "b", "unused" }) do
  local tile = sprite:newTile(source)
  tile.image:clear(indexed and index or app.pixelColor.rgba(20 + index, 30, 40, 255))
  tile.data = "source-" .. key
  tile.properties("aigengame.spa").tile_key = key
  tile.properties("outside.spa").large = 9007199254740993
end
if app.params.unkeyed then
  source:tile(tonumber(app.params.unkeyed)).properties("aigengame.spa").tile_key = nil
end
if app.params.duplicate then source:tile(3).properties("aigengame.spa").tile_key = "a" end
if app.params.invalid_key then source:tile(1).properties("aigengame.spa").tile_key = 123 end
local image = Image(3, 1, ColorMode.TILEMAP)
image:putPixel(0, 0, 1 | 0xe0000000)
image:putPixel(1, 0, 2 | 0x80000000)
image:putPixel(2, 0, app.params.flagged_empty and 0xe0000000 or 0)
sprite:newCel(map, 1, image, Point(-3, 7))
app.activeLayer = map
app.command.NewFrame { content = "cellinked" }
assert(map:cel(1).image == map:cel(2).image)
if app.params.separate_frames then
  app.activeFrame = 2
  app.command.UnlinkCel()
  map:cel(1).image:putPixel(1, 0, 0)
  map:cel(2).image:putPixel(0, 0, 0)
end
app.command.NewLayer { tilemap = true, ask = false, gridBounds = Rectangle(0, 0, 2, 3) }
local peer, generated = app.activeLayer, app.activeLayer.tileset
peer.name, peer.tileset = "peer", source
sprite:deleteTileset(generated)
sprite:newCel(peer, 2, Image(image), Point(4, -2))
local group = sprite:newGroup()
group.name = "nested"
peer.parent = group
local destination = sprite:newTileset(
  Grid {
    x = 0,
    y = 0,
    width = tonumber(app.params.width or "2"),
    height = tonumber(app.params.height or "3"),
  },
  1
)
destination.name, destination.baseIndex = "destination", -3
for index, key in ipairs({ "b", "a", "extra" }) do
  local tile = sprite:newTile(destination)
  tile.image:clear(
    indexed and (index == 1 and tonumber(app.params.high_index or "7") or 2)
      or app.pixelColor.rgba(90 + index, 60, 30, 255)
  )
  tile.data = "destination-" .. key
  tile.properties("aigengame.spa").tile_key = key
  tile.properties("outside.spa").large = 9007199254740993
  tile.properties("outside.spa").point = Point(index, -index)
  tile.properties("outside.spa").binary = string.char(255, 254, index)
end
if app.params.target_duplicate then
  destination:tile(3).properties("aigengame.spa").tile_key = "a"
end
if app.params.target_missing then
  destination:tile(2).properties("aigengame.spa").tile_key = "other"
end
assert(sprite:saveAs(app.params.source))
sprite:close()
