-- Read-only independent inspection of stored pixels, including invisible Cels.
local sprite = assert(app.open(app.params.source), "could not open wizard source")
local colors = {}
local nonbinary_alpha = 0
local pixels = 0
local noninteger_positions = 0
for _, cel in ipairs(sprite.cels) do
  if cel.position.x % 1 ~= 0 or cel.position.y % 1 ~= 0 then
    noninteger_positions = noninteger_positions + 1
  end
  for y = 0, cel.image.height - 1 do
    for x = 0, cel.image.width - 1 do
      local pixel = cel.image:getPixel(x, y)
      local alpha = app.pixelColor.rgbaA(pixel)
      if alpha ~= 0 and alpha ~= 255 then nonbinary_alpha = nonbinary_alpha + 1 end
      if alpha ~= 0 then
        local key = string.format(
          "#%02x%02x%02x",
          app.pixelColor.rgbaR(pixel),
          app.pixelColor.rgbaG(pixel),
          app.pixelColor.rgbaB(pixel)
        )
        colors[key] = true
      end
      pixels = pixels + 1
    end
  end
end
local palette = {}
for color in pairs(colors) do
  palette[#palette + 1] = color
end
table.sort(palette)
local result = {
  stored_colors = palette,
  nonbinary_alpha = nonbinary_alpha,
  stored_pixels = pixels,
  noninteger_positions = noninteger_positions,
  srgb = sprite.colorSpace == ColorSpace { sRGB = true },
  no_profile = sprite.colorSpace == ColorSpace(),
}
sprite:close()
local output = assert(io.open(app.params.out, "wb"))
output:write(json.encode(result))
output:close()
