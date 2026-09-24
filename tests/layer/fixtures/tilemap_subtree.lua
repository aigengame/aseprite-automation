local sprite = Sprite(8, 8, ColorMode.RGB)
app.activeSprite = sprite
app.activeLayer = sprite.layers[1]
app.transaction(function() assert(app.command.BackgroundFromLayer()) end)
assert(sprite.layers[1].isBackground)
local group = sprite:newGroup()
group.name = "mixed"
app.activeSprite = sprite
app.activeLayer = group
assert(app.command.NewLayer { tilemap = true })
local tilemap = assert(group.layers[#group.layers])
assert(tilemap.isTilemap)
assert(group.layers[1] == tilemap)
local regular = sprite:newLayer()
regular.name = "regular"
regular.parent = group
assert(sprite:saveAs(app.params.out))
sprite:close()
