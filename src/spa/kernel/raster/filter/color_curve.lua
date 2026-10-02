-- Aseprite owns the curve interpolation, endpoint extension, and projection.
local module = {}
local application = dofile(app.params.filter_application)

function module.apply(sprite, payload, uuids)
  local points, facts = {}, {}
  for _, point in ipairs(payload.points) do
    points[#points + 1] = Point(point.input, point.output)
    facts[#facts + 1] = { input = point.input, output = point.output }
  end
  local result = application.apply_pixels(sprite, payload, uuids, "Color Curve", function(flags)
    assert(
      app.command.ColorCurve { ui = false, channels = flags, curve = points },
      "Native Color Curve failed"
    )
    return true
  end)
  if not result.rejection then result.points = facts end
  return result
end

return module
