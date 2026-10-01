-- Aseprite owns Brightness/Contrast arithmetic and quantization.
local module = {}
local application = dofile(app.params.filter_application)

function module.apply(sprite, payload, uuids)
  local result = application.apply(sprite, payload, uuids, "Brightness/Contrast", function(flags)
    if payload.brightness == 0 and payload.contrast == 0 then return false end
    assert(
      app.command.BrightnessContrast {
        ui = false,
        channels = flags,
        brightness = payload.brightness,
        contrast = payload.contrast,
      },
      "Native Brightness/Contrast failed"
    )
    return true
  end)
  if not result.rejection then
    result.cel_effects = nil
    result.brightness = payload.brightness
    result.contrast = payload.contrast
  end
  return result
end

return module
