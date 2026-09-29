local sprite = Sprite(4, 3, ColorMode.RGB)
app.activeSprite = sprite
app.activeLayer = sprite.layers[1]
app.command.NewLayer { reference = true }
local reference = app.activeLayer
local group = sprite:newGroup()
group.name = "Group"
group.stackIndex = 3
reference.stackIndex = 2
assert(sprite.layers[2].isReference and sprite.layers[3].isGroup)
assert(sprite:saveAs(app.params.out))
sprite:close()
