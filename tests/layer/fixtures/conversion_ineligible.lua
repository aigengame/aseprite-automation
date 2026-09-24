local variant = app.params.mode
local sprite = Sprite(3, 2, ColorMode.RGB)
local layer = sprite.layers[1]
layer.name = "subject"
if variant == "hidden" then
  layer.isVisible = false
elseif variant == "locked" then
  layer.isEditable = false
elseif variant == "hidden-parent" then
  local group = sprite:newGroup()
  group.name = "group"
  layer.parent = group
  group.isVisible = false
elseif variant == "group" then
  layer.name = "base"
  layer = sprite:newGroup()
  layer.name = "subject"
else
  error("unknown fixture variant")
end
assert(sprite:saveAs(app.params.out))
sprite:close()
