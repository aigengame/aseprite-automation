local sprite = assert(app.open(app.params.source))
local points = {}
for _, point in ipairs(json.decode(app.params.points)) do
  points[#points + 1] = Point(point.input, point.output)
end
local channels = 0
for _, name in ipairs(json.decode(app.params.channels)) do
  channels = channels | FilterChannels[name:upper()]
end
app.command.ColorCurve { ui = false, curve = points, channels = channels }
sprite:saveAs(app.params.target)
sprite:close()
