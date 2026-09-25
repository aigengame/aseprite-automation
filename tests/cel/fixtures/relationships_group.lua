local sprite = Sprite(4, 4, ColorMode.RGB)
local group = sprite:newGroup()
group.name = "Parent"
local child = sprite:newLayer()
child.name = "Child"
child.parent = group
sprite:newEmptyFrame(2)
local image = Image(2, 2, ColorMode.RGB)
image:drawPixel(0, 0, Color { r = 30, g = 40, b = 50, a = 255 })
sprite:newCel(child, 1, image, Point(1, 1))
assert(sprite:saveAs(app.params.out))
sprite:close()
