local sprite = Sprite(4, 3, ColorMode.RGB)
app.activeSprite = sprite
app.activeLayer = sprite.layers[1]
app.activeFrame = sprite.frames[1]
app.bgColor = Color { r = 10, g = 20, b = 30, a = 255 }
app.command.BackgroundFromLayer()
for number = 2, 3 do
  sprite:newEmptyFrame(number)
end
for number = 1, 3 do
  sprite.layers[1]:cel(number).image:putPixel(0, 0, app.pixelColor.rgba(number * 40, 0, 0, 255))
end
assert(sprite:saveAs(app.params.out))
sprite:close()
