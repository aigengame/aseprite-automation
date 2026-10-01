local sprite = Sprite(2, 1, ColorMode.RGB)
local ordinary = sprite.layers[1]
sprite.gridBounds = Rectangle(0, 0, 1, 1)
app.command.NewLayer { tilemap = true, ui = false }
local layer = app.activeLayer
layer.name = "Direct"
local tileset = layer.tileset
local tile = sprite:newTile(tileset)
tile.image:clear(app.pixelColor.rgba(80, 40, 20, 100))
tile.properties("aigengame.spa").tile_key = "existing-key"
tile.properties("other.plugin").retained = { point = Point(2, 3), values = { 1, "two", true } }
local unused = sprite:newTile(tileset)
unused.image:clear(app.pixelColor.rgba(20, 30, 40, 90))
local map = Image(2, 1, ColorMode.TILEMAP)
map:clear(1)
sprite:newCel(layer, 1, map)
sprite:deleteLayer(ordinary)
app.activeCel = layer:cel(1)
assert(app.command.NewFrame { content = "cellinked" })
if app.params.linked ~= "true" then
  sprite:deleteCel(layer:cel(2))
  sprite:newCel(layer, 2, Image(map))
end
app.activeFrame = sprite.frames[2]
assert(app.command.NewFrame { content = "cellinked" })
for _, name in ipairs({ "Hidden", "Locked" }) do
  assert(app.command.NewLayer { tilemap = true, ui = false })
  local referring = app.activeLayer
  local unused_tileset = referring.tileset
  referring.tileset = tileset
  sprite:deleteTileset(unused_tileset)
  referring.name = name
  sprite:newCel(referring, 3, Image(map), Point(0, 0))
  if name == "Hidden" then referring.isVisible = false end
  if name == "Locked" then referring.isEditable = false end
end
assert(sprite:saveAs(app.params.source))
sprite:close()
