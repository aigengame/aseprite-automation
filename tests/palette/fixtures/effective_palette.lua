if app.params.mode == "create" then
  local sprite = Sprite(1, 1, ColorMode.INDEXED)
  local palette = Palette(2)
  palette:setColor(0, Color { r = 0, g = 0, b = 0, a = 0 })
  palette:setColor(1, Color { r = 241, g = 82, b = 65, a = 255 })
  sprite:setPalette(palette)
  for _ = 2, 5 do
    sprite:newEmptyFrame()
  end
  assert(sprite:saveAs(app.params.source))
  sprite:close()
  return
end

local palettes = dofile(app.params.effective_palette)
local sprite = assert(app.open(app.params.source))
local sentinel = Sprite(1, 1, ColorMode.RGB)
sentinel:newEmptyFrame()
app.activeFrame = sentinel.frames[2]
local active_frame = app.activeFrame
local observations = {}
for _, requested in ipairs { 5, 1, 2, 3, 4 } do
  local palette, change_frame = palettes.resolve(sprite, requested)
  local color = palette:getColor(1)
  observations[#observations + 1] = {
    requested_frame_number = requested,
    palette_frame_number = change_frame,
    native_frame_number = palette.frame.frameNumber,
    color = { color.red, color.green, color.blue, color.alpha },
  }
end
local output = assert(io.open(app.params.out, "wb"))
output:write(json.encode {
  observations = observations,
  active_context_preserved = app.activeSprite == sentinel and app.activeFrame == active_frame,
})
output:close()
sentinel:close()
sprite:close()
