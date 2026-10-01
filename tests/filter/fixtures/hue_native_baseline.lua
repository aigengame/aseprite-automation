-- Independent direct command oracle: no packaged SPA Filter code or mode mapping.
local sprite = assert(app.open(app.params.source))
app.activeSprite = sprite
app.activeLayer = sprite.layers[1]
app.activeFrame = sprite.frames[1]
app.range:clear()
if app.params.kind ~= "indexed-palette-entries" then
  app.range.layers = { sprite.layers[1] }
  app.range.frames = { 1 }
end
app.range.colors = app.params.kind == "pixels" and {} or { 1 }
-- Indexed color filtering without an explicit pixel mask edits the Palette.
-- A Canvas Selection selects the intended native pixel application.
sprite.selection = app.params.kind == "indexed-palette-entries" and Selection()
  or Selection(Rectangle(0, 0, sprite.width, sprite.height))
assert(app.command.HueSaturation {
  ui = false,
  mode = app.params.native_mode,
  channels = tonumber(app.params.channels),
  hue = tonumber(app.params.hue),
  saturation = tonumber(app.params.saturation),
  lightness = tonumber(app.params.lightness),
  alpha = tonumber(app.params.alpha),
})
assert(sprite:saveAs(app.params.target))
sprite:close()
