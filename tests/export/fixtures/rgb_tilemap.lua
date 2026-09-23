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
assert(sprite:saveAs(app.params.out))
sprite:close()
