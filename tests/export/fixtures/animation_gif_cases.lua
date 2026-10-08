local scenario = app.params.scenario
local sprite = Sprite(scenario == "lossy" and 257 or 1, 1, ColorMode.RGB)
for frame = 1, 3 do
  if frame > 1 then sprite:newEmptyFrame() end
  local image = Image(sprite.spec)
  if scenario == "lossy" then
    for x = 0, 256 do
      image:putPixel(x, 0, app.pixelColor.rgba(x % 256, math.floor(x / 256), frame * 60, 255))
    end
  elseif frame == 1 then
    image:clear(app.pixelColor.rgba(255, 0, 0, 255))
  elseif frame == 3 then
    image:clear(app.pixelColor.rgba(0, 255, 0, 255))
  end
  sprite:newCel(sprite.layers[1], frame, image)
  sprite.frames[frame].duration = (scenario == "short" and frame == 2) and 0.009 or 0.019
end
assert(sprite:saveAs(app.params.out))
sprite:close()
