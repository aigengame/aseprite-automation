local sprite = Sprite(3, 2, ColorMode.RGB)
app.activeSprite = sprite
app.activeLayer = sprite.layers[1]
app.activeFrame = sprite.frames[1]
app.bgColor = Color { r = 10, g = 20, b = 30, a = 255 }
assert(app.command.BackgroundFromLayer())
local layer = sprite.layers[1]
if app.params.mode == "hidden" then
  layer.isVisible = false
elseif app.params.mode == "locked" then
  layer.isEditable = false
else
  error("unknown fixture variant")
end
assert(sprite:saveAs(app.params.out))
sprite:close()
