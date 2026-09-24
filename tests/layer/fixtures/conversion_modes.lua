local mode = app.params.mode
local sprite = Sprite(3, 2, mode == "grayscale" and ColorMode.GRAY or ColorMode.INDEXED)
sprite.layers[1].name = "subject"
if mode == "grayscale" then
  sprite.layers[1]:cel(1).image:putPixel(1, 0, app.pixelColor.graya(200, 128))
else
  local palette = Palette(3)
  palette:setColor(0, Color { r = 0, g = 0, b = 0, a = 0 })
  palette:setColor(1, Color { r = 241, g = 82, b = 65, a = 255 })
  palette:setColor(2, Color { r = 20, g = 40, b = 200, a = 255 })
  sprite:setPalette(palette)
  sprite.layers[1]:cel(1).image:putPixel(1, 0, 1)
end
sprite:newEmptyFrame(2)
assert(sprite:saveAs(app.params.out))
sprite:close()
