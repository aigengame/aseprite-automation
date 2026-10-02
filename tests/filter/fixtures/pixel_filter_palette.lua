local sprite = Sprite(3, 1, ColorMode.INDEXED)
local palette = Palette(256)
for index = 0, 255 do
  palette:setColor(index, Color { r = index, g = index, b = index, a = index == 0 and 0 or 255 })
end
sprite:setPalette(palette)
local first = sprite.cels[1]
first.image:drawPixel(0, 0, 127)
first.image:drawPixel(1, 0, 128)
first.image:drawPixel(2, 0, 255)
app.activeCel = first
assert(app.command.NewFrame { content = "cellinked" })
local second = sprite.layers[1]:cel(2)
second.position = Point(1, 0)
assert(first.image == second.image)
sprite:newFrame(2)
assert(sprite:saveAs(app.params.source))
sprite:close()
