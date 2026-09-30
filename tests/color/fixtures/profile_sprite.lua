local sprite
if app.params.action == "create" then
  local mode = ColorMode.RGB
  if app.params.mode == "grayscale" then mode = ColorMode.GRAY end
  if app.params.mode == "indexed" then mode = ColorMode.INDEXED end
  sprite = Sprite(3, 1, mode)
  sprite:assignColorSpace(ColorSpace { sRGB = true })
  local palette = sprite.palettes[1]
  palette:resize(4)
  for i = 0, 3 do
    palette:setColor(i, Color { r = 32 + i * 40, g = 70 + i * 30, b = 130 - i * 20, a = 255 })
  end
  local image = sprite.cels[1].image
  for x = 0, 2 do
    local pixel = app.pixelColor.rgba(48 + x * 30, 96 + x * 30, 144 - x * 20, 255 - x * 60)
    if mode == ColorMode.GRAY then pixel = app.pixelColor.graya(48 + x * 30, 255 - x * 60) end
    if mode == ColorMode.INDEXED then pixel = x + 1 end
    image:drawPixel(x, 0, pixel)
  end
  assert(sprite:saveAs(app.params.source))
else
  sprite = assert(app.open(app.params.source))
end
local pixels = {}
for pixel in sprite.cels[1].image:pixels() do
  pixels[#pixels + 1] = pixel()
end
local entries = {}
for i = 0, #sprite.palettes[1] - 1 do
  entries[#entries + 1] = sprite.palettes[1]:getColor(i).rgbaPixel
end
local facts = {
  none = sprite.colorSpace == ColorSpace(),
  srgb = sprite.colorSpace == ColorSpace { sRGB = true },
  name = sprite.colorSpace.name,
  pixels = pixels,
  entries = entries,
}
sprite:close()
print(json.encode(facts))
