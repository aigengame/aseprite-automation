-- Observe explicit Tilemap creation, shared binding, and temporary Tileset removal.
local module = {}

function module.observes()
  local previous = { sprite = app.activeSprite, layer = app.activeLayer, frame = app.activeFrame }
  local sprite, path
  local ok = pcall(function()
    path = app.fs.joinPath(app.fs.tempPath, "spa-tile-layer-" .. tostring(Uuid()) .. ".aseprite")
    assert(not app.fs.isFile(path))
    sprite = Sprite(4, 4)
    app.activeSprite = sprite
    assert(app.command.NewLayer { tilemap = true, ask = false, gridBounds = Rectangle(0, 0, 2, 3) })
    local created = app.activeLayer
    local tileset = created.tileset
    tileset.name, tileset.baseIndex = "probe", 77
    assert(#created.cels == 0 and #sprite.tilesets == 1)
    assert(app.command.NewLayer { tilemap = true, ask = false, gridBounds = Rectangle(0, 0, 2, 3) })
    local shared = app.activeLayer
    local temporary = shared.tileset
    assert(temporary ~= tileset and #sprite.tilesets == 2)
    shared.tileset = tileset
    sprite:deleteTileset(temporary)
    assert(#sprite.tilesets == 1 and shared.tileset == created.tileset)
    assert(sprite:saveAs(path))
    sprite:close()
    sprite = nil
    sprite = assert(app.open(path))
    assert(#sprite.layers == 3 and #sprite.tilesets == 1)
    created, shared, tileset = sprite.layers[2], sprite.layers[3], sprite.tilesets[1]
    assert(not sprite.layers[1].isTilemap)
    assert(created.tileset == tileset and shared.tileset == tileset)
    assert(#created.cels == 0 and #shared.cels == 0)
    assert(tileset.name == "probe" and tileset.baseIndex == 77 and #tileset == 1)
    assert(tileset.grid.origin.x == 0 and tileset.grid.origin.y == 0)
    assert(tileset.grid.tileSize.width == 2 and tileset.grid.tileSize.height == 3)
  end)
  if sprite ~= nil then pcall(function() sprite:close() end) end
  if path ~= nil then pcall(function() os.remove(path) end) end
  if previous.sprite ~= nil and previous.sprite.isValid then
    pcall(function() app.activeSprite = previous.sprite end)
    pcall(function() app.activeLayer = previous.layer end)
    pcall(function() app.activeFrame = previous.frame end)
  end
  return ok
end

return module
