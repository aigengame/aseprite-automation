local mode = app.params.mode == "indexed" and ColorMode.INDEXED or ColorMode.RGB
local sprite = Sprite(3, 2, mode)
sprite.layers[1].name = "Destination"
sprite:newEmptyFrame()
sprite:newEmptyFrame()
for _, cel in ipairs(sprite.cels) do
  sprite:deleteCel(cel)
end
if app.params.profile == "srgb" then
  sprite:assignColorSpace(ColorSpace { sRGB = true })
elseif app.params.profile == "icc" then
  sprite:assignColorSpace(ColorSpace { fromFile = app.params.icc })
else
  sprite:assignColorSpace(ColorSpace())
end
if mode == ColorMode.INDEXED then
  local palette = sprite.palettes[1]
  palette:resize(4)
  palette:setColor(0, Color { r = 0, g = 0, b = 0, a = 0 })
  palette:setColor(1, Color { r = 200, g = 20, b = 40, a = 255 })
  palette:setColor(2, Color { r = 10, g = 80, b = 160, a = 128 })
  palette:setColor(3, Color { r = 17, g = 31, b = 53, a = 255 })
  sprite.transparentColor = tonumber(app.params.mask or "0")
end
assert(sprite:saveAs(app.params.out))
sprite:close()
