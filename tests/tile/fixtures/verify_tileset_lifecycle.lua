-- Independent native oracle: do not use the SPA handlers to infer success.
local sprite = assert(app.open(app.params.source))
local map = sprite.layers[2]
assert(map.name == "map")
local destination = sprite.tilesets[2]
assert(map.tileset == destination)
assert(map:cel(1).image == map:cel(2).image, "Linked Cels were detached")
assert(map:cel(1).position == Point(-3, 7))
local explicit = app.params.explicit == "true"
assert(map:cel(1).image:getPixel(0, 0) == (2 | 0xe0000000))
assert(map:cel(1).image:getPixel(1, 0) == (explicit and 0 or (1 | 0x80000000)))
assert(map:cel(1).image:getPixel(2, 0) == 0)
local peer = sprite.layers[3].layers[1]
assert(peer.name == "peer" and peer.tileset == sprite.tilesets[1])
assert(peer:cel(2).image:getPixel(0, 0) == (1 | 0xe0000000))
assert(peer:cel(2).position == Point(4, -2))
for index, key in ipairs({ "b", "a", "extra" }) do
  local tile = destination:tile(index)
  assert(tile.data == "destination-" .. key)
  assert(tile.properties("outside.spa").large == 9007199254740993)
  assert(tile.properties("outside.spa").point == Point(index, -index))
  assert(tile.properties("outside.spa").binary == string.char(255, 254, index))
end
sprite:close()
