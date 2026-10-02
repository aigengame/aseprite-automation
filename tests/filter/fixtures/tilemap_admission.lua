local tiles = dofile(app.params.filter_tiles)
local manual = { tileset_mode = "manual" }
assert(tiles.admit(manual, true, TilesetMode.MANUAL) == nil)
assert(tiles.admit({}, true, TilesetMode.MANUAL):find("explicit"))
assert(tiles.admit(manual, false, TilesetMode.MANUAL):find("capability"))
assert(tiles.admit(manual, true, TilesetMode.AUTO):find("differs"))
assert(tiles.admit(manual, true, TilesetMode.STACK):find("differs"))
assert(tiles.admit(manual, true, nil):find("differs"))
