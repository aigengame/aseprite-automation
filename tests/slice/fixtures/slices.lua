local sprite = Sprite(12, 10, ColorMode.RGB)
sprite.cels[1].image:putPixel(1, 1, app.pixelColor.rgba(10, 20, 30, 255))
for _ = 2, 6 do
  sprite:newEmptyFrame()
end
local first = sprite:newSlice(Rectangle(-2, 3, 6, 4))
first.name = "same"
first.data = "first"
first.color = Color { r = 12, g = 34, b = 56, a = 78 }
first.center = Rectangle(1, 1, 2, 2)
first.pivot = Point(-1, 5)
first.properties.fixture = "preserve"
local second = sprite:newSlice(Rectangle(4, 2, 3, 5))
second.name = "same"
second.data = "second"
assert(sprite:saveAs(app.params.target))
sprite:close()
