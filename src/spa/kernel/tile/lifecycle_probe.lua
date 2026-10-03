-- Observe append, Key assignment, whole-record move/delete, links, and orphan context.
local module = {}

function module.observes()
  local range = app.range
  local previous = {
    sprite = app.activeSprite,
    layer = app.activeLayer,
    frame = app.activeFrame,
    tiles = range.tiles,
    colors = range.colors,
    empty = range.isEmpty,
  }
  if previous.sprite ~= nil then
    previous.layers, previous.frames, previous.slices = range.layers, range.frames, range.slices
  end
  local sprite, path
  local ok = pcall(function()
    path =
      app.fs.joinPath(app.fs.tempPath, "spa-tile-lifecycle-" .. tostring(Uuid()) .. ".aseprite")
    assert(not app.fs.isFile(path))
    sprite = Sprite(4, 4)
    app.activeSprite = sprite
    assert(app.command.NewLayer { tilemap = true, ask = false, gridBounds = Rectangle(0, 0, 2, 2) })
    local layer, tileset = app.activeLayer, app.activeLayer.tileset
    tileset.baseIndex = 37
    local first, second = sprite:newTile(tileset), sprite:newTile(tileset)
    assert(first.index == 1 and second.index == 2 and #tileset == 3)
    first.properties("aigengame.spa").tile_key = "first"
    second.properties("aigengame.spa").tile_key = "second"
    first.data, first.color = "preserved", Color { r = 17, g = 29, b = 41, a = 255 }
    first.properties.note = "default"
    first.properties("example.plugin").integer = 9007199254740993
    first.properties("example.plugin").point = Point(2, -3)
    first.properties("example.plugin").binary = string.char(255, 254)
    local content = Image(2, 2, ColorMode.RGB)
    content:clear(app.pixelColor.rgba(17, 29, 41, 255))
    first.image = content
    local flags = app.pixelColor.TILE_XFLIP | app.pixelColor.TILE_YFLIP | app.pixelColor.TILE_DFLIP
    local original = Image(2, 1, ColorMode.TILEMAP)
    original:putPixel(0, 0, 1 | flags)
    original:putPixel(1, 0, flags)
    sprite:newCel(layer, 1, original, Point(-2, 3))
    app.activeFrame = sprite.frames[1]
    assert(app.command.NewFrame { content = "cellinked" })
    assert(layer:cel(1).image == layer:cel(2).image)
    app.transaction(function()
      app.range.tiles = { 1 }
      assert(app.command.MoveTiles { before = 3 })
      assert(layer:cel(1).image:getPixel(0, 0) == 1 | flags)
      local final = Image(original)
      final:putPixel(0, 0, 2 | flags)
      layer:cel(1).image = final
      sprite:deleteTile(tileset, 1)
      assert(layer:cel(1).image:getPixel(0, 0) == 2 | flags)
      final:putPixel(0, 0, 1 | flags)
      layer:cel(1).image = final
    end)
    local orphan = sprite:newTileset(Grid { x = 0, y = 0, width = 2, height = 2 }, 1)
    sprite:newTile(orphan).properties("aigengame.spa").tile_key = "a"
    sprite:newTile(orphan).properties("aigengame.spa").tile_key = "b"
    app.transaction(function()
      assert(
        app.command.NewLayer { tilemap = true, ask = false, gridBounds = Rectangle(0, 0, 2, 2) }
      )
      local temporary, generated = app.activeLayer, app.activeLayer.tileset
      temporary.tileset = orphan
      sprite:deleteTileset(generated)
      app.range.tiles = { 2 }
      assert(app.command.MoveTiles { before = 1 })
      sprite:deleteLayer(temporary)
    end)
    assert(sprite:saveAs(path))
    sprite:close()
    sprite = nil
    sprite = assert(app.open(path))
    layer, tileset = sprite.layers[2], sprite.tilesets[1]
    first = tileset:tile(1)
    assert(#sprite.layers == 2 and #sprite.tilesets == 2 and #tileset == 2)
    assert(tileset.baseIndex == 37 and first.properties("aigengame.spa").tile_key == "first")
    assert(
      first.data == "preserved" and first.color.red == 17 and first.image.bytes == content.bytes
    )
    assert(first.properties.note == "default")
    assert(first.properties("example.plugin").integer == 9007199254740993)
    assert(first.properties("example.plugin").point.y == -3)
    assert(first.properties("example.plugin").binary == string.char(255, 254))
    assert(layer:cel(1).image == layer:cel(2).image)
    assert(
      layer:cel(1).image:getPixel(0, 0) == 1 | flags and layer:cel(1).image:getPixel(1, 0) == flags
    )
    assert(sprite.tilesets[2]:tile(1).properties("aigengame.spa").tile_key == "b")
  end)
  if sprite ~= nil then pcall(function() sprite:close() end) end
  if path ~= nil then pcall(function() os.remove(path) end) end
  if previous.sprite ~= nil and previous.sprite.isValid then
    pcall(function() app.activeSprite = previous.sprite end)
    pcall(function() app.activeLayer = previous.layer end)
    pcall(function() app.activeFrame = previous.frame end)
    pcall(function()
      if previous.empty then
        app.range:clear()
      else
        app.range.layers, app.range.frames = previous.layers, previous.frames
        app.range.slices = previous.slices
      end
    end)
  end
  pcall(function()
    app.range.tiles, app.range.colors = previous.tiles, previous.colors
  end)
  return ok
end

return module
