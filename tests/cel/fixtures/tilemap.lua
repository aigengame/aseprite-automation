local sprite = Sprite(8, 6, ColorMode.RGB)
sprite.gridBounds = Rectangle(0, 0, 2, 2)
app.activeSprite = sprite
app.activeLayer = sprite.layers[1]
app.command.NewLayer { tilemap = true }
local layer = sprite.layers[2]
assert(layer.isTilemap)
app.useTool {
  tool = "pencil",
  color = app.pixelColor.rgba(250, 0, 0, 255),
  layer = layer,
  tilesetMode = TilesetMode.STACK,
  points = { Point(4, 2) },
}
local cel = assert(layer:cel(1))
assert(cel.image.colorMode == ColorMode.TILEMAP)
assert(cel.position.x == 4 and cel.position.y == 2)
assert(cel.image.width == 1 and cel.image.height == 1)
assert(sprite:saveAs(app.params.out))
sprite:close()
