local sprite = assert(app.open(app.params.source))
local function color(value)
  if value.kind == "rgba" then
    return Color { r = value.red, g = value.green, b = value.blue, a = value.alpha }
  elseif value.kind == "grayscale" then
    return Color { gray = value.gray, alpha = value.alpha }
  end
  return Color { index = value.index }
end
local channels = 0
for _, name in ipairs(json.decode(app.params.channels)) do
  channels = channels | FilterChannels[name:upper()]
end
app.command.ReplaceColor {
  ui = false,
  channels = channels,
  from = color(json.decode(app.params.from)),
  to = color(json.decode(app.params.to)),
  tolerance = tonumber(app.params.tolerance),
}
sprite:saveAs(app.params.target)
sprite:close()
