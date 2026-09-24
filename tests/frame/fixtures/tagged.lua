local sprite = Sprite(3, 2, ColorMode.RGB)
sprite:newEmptyFrame(2)
sprite.frames[1].duration = 0.12
sprite.frames[2].duration = 0.34
local tag = sprite:newTag(1, 2)
tag.name = "walk"
assert(sprite:saveAs(app.params.out))
sprite:close()
