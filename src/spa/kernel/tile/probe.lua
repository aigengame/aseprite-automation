-- Observe Tile inspection and explicit empty Cel creation independently.
local module = {}

function module.observes()
  local previous = { sprite = app.activeSprite, layer = app.activeLayer, frame = app.activeFrame }
  local sprite, path
  local inspected, created = false, false
  pcall(function()
    local candidate =
      app.fs.joinPath(app.fs.tempPath, "spa-tile-probe-" .. tostring(Uuid()) .. ".aseprite")
    assert(not app.fs.isFile(candidate), "Tile probe path already exists")
    path = candidate
    sprite = Sprite(8, 8, ColorMode.RGB)
    sprite.gridBounds = Rectangle(0, 0, 2, 3)
    app.activeSprite = sprite
    assert(app.command.NewLayer { tilemap = true, ui = false })
    local layer = app.activeLayer
    assert(layer.isTilemap and layer.tileset == sprite.tilesets[1])
    local tileset = layer.tileset
    tileset.baseIndex = 7
    local tile = sprite:newTile(tileset)
    tile.properties("aigengame.spa").tile_key = "probe"
    tile.properties.observed = Point(1, 2)
    local flags = app.pixelColor.TILE_XFLIP | app.pixelColor.TILE_YFLIP | app.pixelColor.TILE_DFLIP
    local packed = app.pixelColor.tile(tile.index, flags)
    local image = Image(2, 1, ColorMode.TILEMAP)
    image:clear(0)
    image:putPixel(1, 0, packed)
    sprite:newCel(layer, 1, image, Point(-2, 3))
    local blank_created = pcall(function()
      sprite:newEmptyFrame(2)
      local blank = Image(2, 3, ColorMode.TILEMAP)
      blank:clear(0)
      sprite:newCel(layer, 2, blank, Point(0, 0))
    end)
    assert(sprite:saveAs(path))
    sprite:close()
    sprite = nil
    sprite = assert(app.open(path))
    layer = sprite.layers[2]
    tileset = layer.tileset
    tile = assert(tileset:tile(1))
    assert(layer.isTilemap and tileset == sprite.tilesets[1] and #tileset == 2)
    assert(tileset.baseIndex == 7 and tile.index == 1)
    assert(tile.image.width == 2 and tile.image.height == 3)
    assert(tile.properties("aigengame.spa").tile_key == "probe")
    local found = false
    for key, value in pairs(tile.properties) do
      if key == "observed" then
        assert(value.x == 1 and value.y == 2)
        found = true
      end
    end
    assert(found)
    local grid, cel = tileset.grid, assert(layer:cel(1))
    assert(grid.origin.x == 0 and grid.origin.y == 0)
    assert(grid.tileSize.width == 2 and grid.tileSize.height == 3)
    assert(cel.position.x == -2 and cel.position.y == 3)
    assert(cel.image.colorMode == ColorMode.TILEMAP)
    assert(cel.image.width == 2 and cel.image.height == 1)
    assert(cel.image:getPixel(0, 0) == 0 and cel.image:getPixel(1, 0) == packed)
    assert(app.pixelColor.tileI(packed) == 1 and app.pixelColor.tileF(packed) == flags)
    assert(cel.bounds.x == -2 and cel.bounds.y == 3)
    assert(cel.bounds.width == 4 and cel.bounds.height == 3)
    inspected = true
    if blank_created then
      local blank = assert(layer:cel(2))
      assert(blank.image.colorMode == ColorMode.TILEMAP)
      assert(blank.image.width == 2 and blank.image.height == 3)
      assert(blank.position == Point(0, 0) and blank.opacity == 255 and blank.zIndex == 0)
      assert(blank.image ~= cel.image)
      for value in blank.image:pixels() do
        assert(value() == 0)
      end
      created = true
    end
  end)
  if sprite ~= nil then pcall(function() sprite:close() end) end
  if path ~= nil then pcall(function() os.remove(path) end) end
  if previous.sprite ~= nil and previous.sprite.isValid then
    pcall(function() app.activeSprite = previous.sprite end)
    pcall(function() app.activeLayer = previous.layer end)
    pcall(function() app.activeFrame = previous.frame end)
  end
  return inspected, created
end

return module
