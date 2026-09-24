local sprite = Sprite(3, 2, ColorMode.RGB)
local layer = sprite.layers[1]
layer.isContinuous = true
assert(sprite:saveAs(app.params.out))
sprite:close()
