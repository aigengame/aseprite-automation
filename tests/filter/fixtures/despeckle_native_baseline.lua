-- Independent native oracle: no packaged SPA Filter modules.
local sprite = assert(app.open(app.params.source))
app.activeSprite, app.activeLayer, app.activeFrame = sprite, sprite.layers[1], sprite.frames[1]
app.range:clear()
app.range.layers, app.range.frames, app.range.colors = { sprite.layers[1] }, { 1 }, {}
sprite.selection = Selection(Rectangle(0, 0, sprite.width, sprite.height))
assert(app.command.Despeckle {
  ui = false,
  width = tonumber(app.params.width),
  height = tonumber(app.params.height),
  tiledMode = app.params.tiled_mode,
  channels = tonumber(app.params.channels),
})
assert(sprite:saveAs(app.params.target))
sprite:close()
