-- Verify scoped native rebinding, explicit Empty replacement, and orphan removal.
local module = {}

function module.observes()
  local previous = { sprite = app.activeSprite, layer = app.activeLayer, frame = app.activeFrame }
  local sprite, path
  local ok = pcall(function()
    path =
      app.fs.joinPath(app.fs.tempPath, "spa-tileset-lifecycle-" .. tostring(Uuid()) .. ".aseprite")
    assert(not app.fs.isFile(path))
    sprite = Sprite(8, 8)
    local orphan = sprite:newTileset(Grid { x = 0, y = 0, width = 1, height = 1 }, 1)
    orphan.name = "orphan"
    assert(app.command.NewLayer { tilemap = true, ask = false, gridBounds = Rectangle(0, 0, 2, 2) })
    local selected, source = app.activeLayer, app.activeLayer.tileset
    source.name, source.baseIndex = "source", 37
    local first, second = sprite:newTile(source), sprite:newTile(source)
    first.properties("aigengame.spa").tile_key = "kept"
    second.properties("aigengame.spa").tile_key = "empty"
    first.data = "native record"
    first.properties("example.plugin").integer = 9007199254740993
    first.properties("example.plugin").point = Point(2, -3)
    first.properties("example.plugin").binary = string.char(255, 254)
    first.image:clear(app.pixelColor.rgba(17, 29, 41, 255))
    local content = first.image.bytes
    local flags = app.pixelColor.TILE_XFLIP | app.pixelColor.TILE_YFLIP | app.pixelColor.TILE_DFLIP
    local image = Image(2, 1, ColorMode.TILEMAP)
    image:putPixel(0, 0, 1 | flags)
    image:putPixel(1, 0, 2 | flags)
    sprite:newCel(selected, 1, image, Point(-2, 3))
    app.activeFrame = sprite.frames[1]
    assert(app.command.NewFrame { content = "cellinked" })
    assert(selected:cel(1).image == selected:cel(2).image)
    assert(app.command.NewLayer { tilemap = true, ask = false, gridBounds = Rectangle(0, 0, 2, 2) })
    local shared, generated = app.activeLayer, app.activeLayer.tileset
    shared.tileset = source
    sprite:deleteTileset(generated)
    sprite:newCel(shared, 1, image, Point(1, -3))
    assert(shared:cel(1).image ~= selected:cel(1).image)
    local target = sprite:newTileset(Grid { x = 0, y = 0, width = 3, height = 2 }, 1)
    target.name, target.baseIndex = "target", 77
    sprite:newTile(target).properties("aigengame.spa").tile_key = "unused"
    sprite:newTile(target).properties("aigengame.spa").tile_key = "kept"
    local unchanged = shared:cel(1).image.bytes
    app.transaction(function()
      local final = Image(image)
      final:putPixel(0, 0, 2 | flags)
      final:putPixel(1, 0, 0)
      selected:cel(1).image = Image(selected:cel(1).image)
      selected.tileset = target
      selected:cel(1).image = final
      sprite:deleteTileset(orphan)
    end)
    assert(#sprite.tilesets == 2 and selected.tileset == target and shared.tileset == source)
    assert(selected:cel(1).image == selected:cel(2).image)
    assert(shared:cel(1).image.bytes == unchanged)
    assert(selected:cel(1).position.x == -2 and selected:cel(1).position.y == 3)
    assert(selected:cel(1).bounds.width == 6 and selected:cel(1).bounds.height == 2)
    local rollback = pcall(function()
      app.transaction(function()
        selected:cel(1).image = Image(selected:cel(1).image)
        selected.tileset = source
        selected:cel(1).image = image
        error("rollback probe")
      end)
    end)
    assert(not rollback and selected.tileset == target)
    assert(selected:cel(1).image == selected:cel(2).image)
    assert(selected:cel(1).image:getPixel(0, 0) == 2 | flags)
    assert(selected:cel(1).image:getPixel(1, 0) == 0)
    assert(selected:cel(1).position.x == -2 and selected:cel(1).position.y == 3)
    assert(selected:cel(1).bounds.width == 6 and selected:cel(1).bounds.height == 2)
    assert(shared:cel(1).image.bytes == unchanged)
    assert(sprite:saveAs(path))
    sprite:close()
    sprite = nil
    sprite = assert(app.open(path))
    selected, shared = sprite.layers[2], sprite.layers[3]
    source, target = sprite.tilesets[1], sprite.tilesets[2]
    assert(sprite.width == 8 and sprite.height == 8 and #sprite.tilesets == 2)
    assert(selected.tileset == target and shared.tileset == source)
    assert(source.baseIndex == 37 and target.baseIndex == 77)
    assert(selected:cel(1).image == selected:cel(2).image)
    assert(selected:cel(1).image:getPixel(0, 0) == 2 | flags)
    assert(selected:cel(1).image:getPixel(1, 0) == 0)
    assert(shared:cel(1).image.bytes == unchanged)
    assert(selected:cel(1).position.x == -2 and selected:cel(1).position.y == 3)
    assert(selected:cel(1).bounds.width == 6 and selected:cel(1).bounds.height == 2)
    first = source:tile(1)
    assert(first.image.bytes == content and first.data == "native record")
    assert(first.properties("aigengame.spa").tile_key == "kept")
    assert(first.properties("example.plugin").integer == 9007199254740993)
    assert(first.properties("example.plugin").point.y == -3)
    assert(first.properties("example.plugin").binary == string.char(255, 254))
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
