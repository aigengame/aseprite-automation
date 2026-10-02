-- Independent native checks for facts outside Slice geometry and public user data.
local sprite = assert(app.open(app.params.source))
assert(#sprite.frames == 6 and #sprite.layers == 1)
assert(sprite.layers[1]:cel(1).image:getPixel(1, 1) == app.pixelColor.rgba(10, 20, 30, 255))
local found = false
for _, slice in ipairs(sprite.slices) do
  if slice.properties.fixture == "preserve" then found = true end
end
assert(found, "Slice custom properties were lost")
sprite:close()
