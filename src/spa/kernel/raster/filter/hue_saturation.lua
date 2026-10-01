-- Native Aseprite owns color conversion, Hue wrapping, and Alpha arithmetic.
local module = {}
local application = dofile(app.params.filter_application)
local json_null = json.decode("null")
local modes = {
  ["hsl-multiply"] = "hsl",
  ["hsv-multiply"] = "hsv",
  ["hsl-add"] = "hsl_add",
  ["hsv-add"] = "hsv_add",
  grayscale = "hsl",
}

function module.apply(sprite, payload, uuids)
  local adjustment = payload.adjustment
  if adjustment == json_null then adjustment = nil end
  -- Native unknown mode strings fall back to HSL: never send an unchecked choice.
  local mode = adjustment and assert(modes[adjustment.mode], "Unknown Hue/Saturation mode") or "hsl"
  local hue = adjustment and adjustment.hue or 0
  local saturation = adjustment and adjustment.saturation or 0
  local lightness = adjustment and (adjustment.lightness or adjustment.value) or 0
  local alpha = type(payload.alpha) == "number" and payload.alpha or 0
  local result = application.apply(sprite, payload, uuids, "Hue/Saturation", function(flags)
    if hue == 0 and saturation == 0 and lightness == 0 and alpha == 0 then return false end
    assert(
      app.command.HueSaturation {
        ui = false,
        channels = flags,
        mode = mode,
        hue = hue,
        saturation = saturation,
        lightness = lightness,
        alpha = alpha,
      },
      "Native Hue/Saturation failed"
    )
    return true
  end)
  if not result.rejection then
    result.adjustment = json_null
    if adjustment then
      local fact = { mode = adjustment.mode }
      if adjustment.mode == "grayscale" then
        fact.lightness = lightness
      else
        fact.hue = hue
        fact.saturation = saturation
        if adjustment.mode:sub(1, 3) == "hsv" then
          fact.value = lightness
        else
          fact.lightness = lightness
        end
      end
      result.adjustment = fact
    end
    result.alpha = type(payload.alpha) == "number" and payload.alpha or json_null
  end
  return result
end

return module
