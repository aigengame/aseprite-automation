-- Independent Aseprite command baseline for extreme Filter values.
local sprite = assert(app.open(app.params.source))
app.activeSprite = sprite
app.activeCel = sprite.cels[1]
app.range:clear()
app.range.layers = { sprite.layers[1] }
app.range.frames = { 1 }
app.range.colors = {}
sprite.selection = Selection(Rectangle(0, 0, sprite.width, sprite.height))
local channels
if app.params.mode == "grayscale" then
  channels = FilterChannels.GRAY
else
  channels = FilterChannels.RED | FilterChannels.GREEN | FilterChannels.BLUE
end
assert(app.command.BrightnessContrast {
  ui = false,
  channels = channels,
  brightness = tonumber(app.params.brightness),
  contrast = tonumber(app.params.contrast),
})
assert(sprite:saveAs(app.params.target))
sprite:close()
