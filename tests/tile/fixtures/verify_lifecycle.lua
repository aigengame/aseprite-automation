-- Independent native assertions: opaque metadata is not reconstructed from SPA JSON.
local sprite = assert(app.open(app.params.source))
local tileset = sprite.tilesets[1]
local expected = json.decode(app.params.order)
assert(#tileset == #expected + 1)
for index, old in ipairs(expected) do
  old = math.tointeger(old)
  local tile = tileset:tile(index)
  local key = ({ "a", "b", "c", "d" })[old]
  assert(tile.properties("aigengame.spa").tile_key == key)
  assert(tile.properties("aigengame.spa").other == "retained-" .. old)
  assert(tile.data == "data-" .. old)
  assert(tile.color.red == 20 + old)
  assert(tile.properties.note == "default-" .. old)
  assert(tile.properties("example").large == 9007199254740993 + old)
  assert(tile.properties("example").point.y == -old)
  assert(tile.properties("example").binary == string.char(255, 254, old))
  assert(tile.image.width == 2 and tile.image.height == 3)
  for pixel in tile.image:pixels() do
    assert(pixel() == app.pixelColor.rgba(10 + old, 30, 40, 255))
  end
end
local orphan = sprite.tilesets[2]
local orphan_order = json.decode(app.params.orphan_order or "[1,2]")
assert(orphan.name == "orphan" and #orphan == #orphan_order + 1)
for index, old in ipairs(orphan_order) do
  old = math.tointeger(old)
  local tile = orphan:tile(index)
  assert(tile.properties("aigengame.spa").tile_key == ({ "x", "y" })[old])
  assert(tile.data == "orphan-data-" .. old)
  assert(tile.properties.note == "orphan-default-" .. old)
  assert(tile.properties("example").binary == string.char(255, 254, old))
  assert(tile.image.width == 2 and tile.image.height == 3)
  for pixel in tile.image:pixels() do
    assert(pixel() == app.pixelColor.rgba(90 + old, 60, 30, 255))
  end
end
local layer, peer
for _, current in ipairs(sprite.layers) do
  if current.name == "map" then layer = current end
  if current.name == "nested" then peer = current.layers[1] end
end
assert(layer:cel(1).image == layer:cel(2).image)
assert(layer:cel(1).position == Point(-3, 7))
assert(peer:cel(2).position == Point(4, -2))
assert(tileset.baseIndex == tonumber(app.params.base_index or "37"))
if app.params.cells then
  local cells = json.decode(app.params.cells)
  for _, cel in ipairs({ layer:cel(1), layer:cel(2), peer:cel(2) }) do
    for x, packed in ipairs(cells) do
      assert(cel.image:getPixel(x - 1, 0) == packed)
    end
  end
end
sprite:close()
