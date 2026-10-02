-- Independent native oracle; no SPA conversion/observation helper is loaded.
local sprite = assert(app.open(app.params.source))
local file = assert(io.open(app.params.options, "rb"))
local request = json.decode(file:read("*a"))
file:close()
app.activeSprite = sprite
app.command.ChangePixelFormat {
  ui = false,
  format = request.format,
  toGray = request.toGray,
  rgbmap = request.rgbmap,
  fitCriteria = request.fitCriteria,
  dithering = request.dithering,
  ditheringMatrix = request.ditheringMatrix,
  ditheringFactor = request.ditheringFactor,
}
assert(sprite:saveAs(app.params.target))
sprite:close()
