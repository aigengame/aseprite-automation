-- Small native documents at the Tile lifecycle's declared geometry/count bounds.
local sprite = Sprite(1, 1, ColorMode.RGB)
local width, height = tonumber(app.params.width or "1"), tonumber(app.params.height or "1")
local tileset = sprite:newTileset(Grid { x = 0, y = 0, width = width, height = height }, 1)
tileset.name = "limits"
app.transaction(function()
  for index = 1, tonumber(app.params.tile_count or "1") - 1 do
    local tile = sprite:newTile(tileset)
    if index ~= tonumber(app.params.unkeyed or "0") then
      tile.properties("aigengame.spa").tile_key = "tile-" .. index
    end
  end
end)
if app.params.frames then
  app.activeSprite = sprite
  assert(app.command.NewLayer {
    tilemap = true,
    ask = false,
    gridBounds = Rectangle(0, 0, width, height),
  })
  local layer, generated = app.activeLayer, app.activeLayer.tileset
  layer.tileset = tileset
  sprite:deleteTileset(generated)
  local image = Image(1024, 512, ColorMode.TILEMAP)
  image:clear(0)
  sprite:newCel(layer, 1, image)
  for _ = 2, tonumber(app.params.frames) do
    assert(app.command.NewFrame { content = "cellinked" })
  end
  for _, cel in ipairs(layer.cels) do
    assert(cel.image == layer:cel(1).image)
  end
  if app.params.peer then
    assert(app.command.NewLayer { tilemap = true, ask = false })
    local peer, unused = app.activeLayer, app.activeLayer.tileset
    peer.tileset = tileset
    sprite:deleteTileset(unused)
    sprite:newCel(peer, 1, image)
  end
end
assert(sprite:saveAs(app.params.source))
sprite:close()
