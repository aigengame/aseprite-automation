-- Five finite source Frames keep an interior Tag separate from the full timeline.
local sprite = Sprite(3, 1, ColorMode.RGB)
for frame = 1, 5 do
  if frame > 1 then sprite:newEmptyFrame() end
  local image = Image(sprite.spec)
  image:putPixel(0, 0, app.pixelColor.rgba(frame * 40, 10, 20, 255))
  image:putPixel(1, 0, app.pixelColor.rgba(10, frame * 30, 20, 128))
  sprite:newCel(sprite.layers[1], frame, image)
  sprite.frames[frame].duration = ({ 19, 27, 103, 40, 60 })[frame] / 1000
end
local tag = sprite:newTag(1, 3)
tag.name = "cast"
tag.aniDir = AniDir.PING_PONG
tag.repeats = 0
assert(sprite:saveAs(app.params.out))
sprite:close()
