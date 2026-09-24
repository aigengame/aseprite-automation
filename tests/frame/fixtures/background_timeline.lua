local sprite = Sprite(3, 2, ColorMode.RGB)
app.activeSprite = sprite
app.activeLayer = sprite.layers[1]
app.activeFrame = sprite.frames[1]
app.bgColor = Color { r = 0, g = 0, b = 0, a = 255 }
app.command.BackgroundFromLayer()
local layer = sprite.layers[1]
local colors = { 30, 60, 90 }
for number = 2, 3 do
  sprite:newEmptyFrame(number)
end
for number = 1, 3 do
  layer:cel(number).image:putPixel(0, 0, app.pixelColor.rgba(colors[number], 0, 0, 255))
end
assert(sprite:saveAs(app.params.out))
sprite:close()
