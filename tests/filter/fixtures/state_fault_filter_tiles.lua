local tiles = dofile(app.params.filter_tiles_real)
local original = tiles.snapshot
function tiles.snapshot(sprite, ...)
  local tile = sprite.tilesets[1]:tile(1)
  if app.pixelColor.rgbaR(tile.image:getPixel(0, 0)) == 120 then
    _G.SPA_TEST_NATIVE_EFFECT_OBSERVED = true
    tile.properties("other.plugin").retained = "corrupted"
  end
  return original(sprite, ...)
end
return tiles
