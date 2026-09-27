local mode = app.params.mode
local sprite = Sprite(3, 2, mode == "grayscale" and ColorMode.GRAY or ColorMode.INDEXED)
app.activeSprite = sprite
app.activeLayer = sprite.layers[1]
app.activeFrame = sprite.frames[1]
if mode == "grayscale" then
  app.bgColor = Color { gray = 60, alpha = 255 }
else
  local palette = Palette(2)
  palette:setColor(0, Color { r = 0, g = 0, b = 0, a = 0 })
  palette:setColor(1, Color { r = 241, g = 82, b = 65, a = 255 })
  sprite:setPalette(palette)
  app.bgColor = Color { index = 1 }
end
app.command.BackgroundFromLayer()
assert(sprite.layers[1].isBackground)
assert(sprite:saveAs(app.params.out))
sprite:close()
