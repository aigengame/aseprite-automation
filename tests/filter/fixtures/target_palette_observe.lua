local sprite = assert(app.open(app.params.source))
local palette_red = {}
for frame = 1, 2 do
  palette_red[frame] = sprite.palettes[frame]:getColor(1).red
end
local result = {
  target_pixel = sprite.layers[1]:cel(1).image:getPixel(0, 0),
  anchor_pixel = sprite.layers[1]:cel(2).image:getPixel(0, 0),
  palette_red = palette_red,
}
local file = assert(io.open(app.params.response, "wb"))
file:write(json.encode(result))
file:close()
sprite:close()
