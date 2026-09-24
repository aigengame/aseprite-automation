local sprite = Sprite(8, 8, ColorMode.RGB)
sprite.useLayerUuids = app.params.uuids == "true"
app.activeSprite = sprite
app.activeLayer = sprite.layers[1]
app.transaction(function() app.command.BackgroundFromLayer() end)
local duplicate = sprite:newLayer()
duplicate.name = "duplicate"
local parent = sprite:newGroup()
parent.name = "parent"
local nested = sprite:newLayer()
nested.name = "duplicate"
nested.parent = parent
local runtime_uuid = tostring(nested.uuid)
assert(sprite:saveAs(app.params.out))
local file = assert(io.open(app.params.runtime_uuid, "wb"))
file:write(runtime_uuid)
file:close()
sprite:close()
