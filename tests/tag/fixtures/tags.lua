local sprite = Sprite(2, 2, ColorMode.RGB)
for _ = 2, 4 do
  sprite:newEmptyFrame()
end
local first = sprite:newTag(1, 2)
first.name = "same"
first.aniDir = AniDir.FORWARD
first.repeats = 0
local second = sprite:newTag(3, 4)
second.name = "same"
second.aniDir = AniDir.REVERSE
second.repeats = 1
assert(sprite:saveAs(app.params.out))
sprite:close()
