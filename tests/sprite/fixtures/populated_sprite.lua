local sprite = Sprite(8, 6, ColorMode.RGB)
sprite:newFrame(1)
sprite.frames[1].duration = 0.12
sprite.frames[2].duration = 0.34

local tag = sprite:newTag(1, 2)
tag.name = "walk"
tag.aniDir = AniDir.PING_PONG
tag.repeats = 2
tag.color = Color { r = 10, g = 20, b = 30, a = 255 }

local group = sprite:newGroup()
group.name = "body"
local child = sprite:newLayer()
child.name = "outline"
child.parent = group
local image = Image(2, 3, ColorMode.RGB)
image:clear(Color { r = 90, g = 80, b = 70, a = 255 })
local child_cel = sprite:newCel(child, 2, image, Point(4, 2))
child_cel.opacity = 123
child_cel.zIndex = 4

local slice = sprite:newSlice(Rectangle(1, 2, 3, 4))
slice.name = "panel"
slice.data = "panel-data"
slice.center = Rectangle(1, 1, 1, 2)
slice.pivot = Point(2, 3)

local tileset = sprite:newTileset(Rectangle(0, 0, 4, 5), 2)
tileset.name = "terrain"
tileset.baseIndex = 7

assert(sprite:saveAs(app.params.out))
sprite:close()
