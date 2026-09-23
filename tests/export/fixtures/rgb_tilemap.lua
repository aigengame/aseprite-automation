local sprite = Sprite(1, 1, ColorMode.RGB)
sprite.gridBounds = Rectangle(0, 0, 1, 1)
app.command.NewLayer{ tilemap=true }
local layer = sprite.layers[2]
assert(layer.isTilemap)
app.useTool{
  tool="pencil",
  color=app.pixelColor.rgba(250, 0, 0, 255),
  layer=layer,
  tilesetMode=TilesetMode.STACK,
  points={Point(0, 0)},
}
assert(layer:cel(1).image.colorMode == ColorMode.TILEMAP)
local arrangement = app.params.arrangement or "visible"
if arrangement == "hidden_layer" then
  layer.isVisible = false
elseif arrangement == "hidden_group" then
  local group = sprite:newGroup()
  layer.parent = group
  group.isVisible = false
else
  assert(arrangement == "visible")
end
assert(sprite:saveAs(app.params.out))
sprite:close()
