-- Independent native fixture and persisted packed-Cell oracle for explicit Cel add.
local function create()
  local modes = { rgb = ColorMode.RGB, grayscale = ColorMode.GRAY, indexed = ColorMode.INDEXED }
  local s = Sprite(3, 3, modes[app.params.mode or "rgb"])
  if s.colorMode == ColorMode.INDEXED then s.transparentColor = 7 end
  local palette = Palette(8)
  for i = 0, 7 do
    palette:setColor(i, Color { r = i * 30, g = 40, b = 60, a = 255 })
  end
  s:setPalette(palette)
  s.data = "preserved Sprite"
  s.layers[1].name = "ordinary"
  s.layers[1]:cel(1).image:putPixel(0, 0, s.colorMode == ColorMode.RGB and 0xff102030 or 1)
  app.activeSprite, app.activeLayer, app.activeFrame = s, s.layers[1], s.frames[1]
  app.command.NewFrame { content = "cellinked" }
  s:newEmptyFrame(3)
  s.frames[2].duration = 0.23
  s.gridBounds = Rectangle(0, 0, 2, 2)
  app.command.NewLayer { tilemap = true, ui = false }
  local layer = app.activeLayer
  layer.name = "map"
  local ts = layer.tileset
  ts.name, ts.baseIndex, ts.data = "terrain", 17, "Tileset metadata"
  local tile = s:newTile(ts)
  tile.image:clear(s.colorMode == ColorMode.RGB and 0xff112233 or 1)
  tile.data = "Tile metadata"
  tile.properties("aigengame.spa").tile_key = "stone"
  tile.properties("example.plugin").anchor = Point(3, -2)
  local image = Image(1, 1, ColorMode.TILEMAP)
  image:putPixel(0, 0, 1 | app.pixelColor.TILE_XFLIP)
  local existing = s:newCel(layer, 2, image, Point(-2, 4))
  existing.opacity, existing.zIndex = 192, -1
  assert(s:saveAs(app.params.source))
  s:close()
end

local function verify()
  local source = assert(app.open(app.params.source))
  local result = assert(app.open(app.params.result))
  assert(result.width == 3 and result.height == 3)
  assert(
    result.colorMode == source.colorMode and result.transparentColor == source.transparentColor
  )
  assert(result.data == source.data and #result.layers == #source.layers)
  assert(#result.frames == #source.frames and #result.tilesets == #source.tilesets)
  for i, frame in ipairs(source.frames) do
    assert(result.frames[i].duration == frame.duration)
  end
  assert(result.layers[1]:cel(1).image == result.layers[1]:cel(2).image)
  for layer_index, layer in ipairs(source.layers) do
    local actual = result.layers[layer_index]
    assert(actual.name == layer.name and actual.data == layer.data)
    if layer.isTilemap then assert(actual.tileset == result.tilesets[1]) end
    for _, before in ipairs(layer.cels) do
      local after = assert(actual:cel(before.frameNumber))
      assert(after.image.bytes == before.image.bytes)
      assert(after.image.width == before.image.width and after.image.height == before.image.height)
      assert(after.position == before.position and after.opacity == before.opacity)
      assert(after.zIndex == before.zIndex)
    end
  end
  for i = 1, #source.tilesets do
    local before = source.tilesets[i]
    local after = result.tilesets[i]
    assert(
      after.name == before.name
        and after.baseIndex == before.baseIndex
        and after.data == before.data
    )
    assert(after.grid.origin == before.grid.origin and after.grid.tileSize == before.grid.tileSize)
    assert(#after == #before)
    for index = 0, #before - 1 do
      local old, new = before:tile(index), after:tile(index)
      assert(new.image.bytes == old.image.bytes and new.data == old.data)
      if index > 0 then
        assert(new.properties("aigengame.spa").tile_key == old.properties("aigengame.spa").tile_key)
        assert(new.properties("example.plugin").anchor == old.properties("example.plugin").anchor)
      end
    end
  end
  assert(#result.palettes == #source.palettes)
  for i = 1, #source.palettes do
    local before = source.palettes[i]
    local after = result.palettes[i]
    assert(#after == #before)
    for j = 0, #before - 1 do
      assert(after:getColor(j) == before:getColor(j))
    end
  end
  local added_count = 0
  for _, number in ipairs({ 1, 3 }) do
    local added = result.layers[2]:cel(number)
    if added then
      added_count = added_count + 1
      assert(added.image.colorMode == ColorMode.TILEMAP)
      assert(added.image.width == tonumber(app.params.width or "2"))
      assert(added.image.height == tonumber(app.params.height or "3"))
      assert(added.position == Point(0, 0) and added.opacity == 255 and added.zIndex == 0)
      for _, other in ipairs(result.cels) do
        assert(other == added or other.image ~= added.image)
      end
      for pixel in added.image:pixels() do
        assert(pixel() == 0, "Tile Cell is not packed zero")
      end
    end
  end
  assert(added_count == tonumber(app.params.added_count or "1"))
  assert(#result.cels == #source.cels + added_count)
  result:close()
  source:close()
end

local ok, message = xpcall(app.params.result and verify or create, debug.traceback)
assert(ok, message)
