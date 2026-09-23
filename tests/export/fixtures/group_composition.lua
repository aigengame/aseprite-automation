app.preferences.experimental.compose_groups = true
local sprite = Sprite(1, 1, ColorMode.RGB)
local group = sprite:newGroup()
group.name = "visible group"
local child = sprite:newLayer()
child.name = "blue"
child.parent = group
child.opacity = 128
local image = Image(1, 1, ColorMode.RGB)
image:putPixel(0, 0, app.pixelColor.rgba(0, 0, 200, 255))
sprite:newCel(child, 1, image)
local hidden = sprite:newLayer()
hidden.name = "hidden red"
hidden.isVisible = false
local hidden_image = Image(1, 1, ColorMode.RGB)
hidden_image:putPixel(0, 0, app.pixelColor.rgba(255, 0, 0, 255))
sprite:newCel(hidden, 1, hidden_image)
assert(sprite:saveAs(app.params.out))
sprite:close()
