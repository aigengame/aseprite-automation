-- Set ambient preferences before the packaged handler runs in this same process.
local handler = assert(app.params.preparation_handler)
local sentinel = Sprite(2, 1, ColorMode.RGB)
sentinel:newEmptyFrame()
app.activeSprite = sentinel
app.activeLayer = sentinel.layers[1]
app.activeFrame = sentinel.frames[2]
app.fgColor = Color { r = 3, g = 5, b = 7, a = 255 }
app.bgColor = Color { r = 11, g = 13, b = 17, a = 255 }
local foreground, background = app.fgColor, app.bgColor
local settings = {
  {
    manage = false,
    files_with_profile = 0,
    missing_profile = 0,
    working_rgb_space = "Display P3",
    rgbmap_algorithm = 1,
    fit_criteria = 4,
    dithering_algorithm = "error-diffusion",
  },
  {
    manage = true,
    files_with_profile = 3,
    missing_profile = 2,
    working_rgb_space = "sRGB",
    rgbmap_algorithm = 2,
    fit_criteria = 0,
    dithering_algorithm = "ordered",
  },
}
local function install(setting)
  for _, key in ipairs({ "manage", "files_with_profile", "missing_profile", "working_rgb_space" }) do
    app.preferences.color[key] = setting[key]
  end
  for _, key in ipairs({ "rgbmap_algorithm", "fit_criteria", "dithering_algorithm" }) do
    app.preferences.quantization[key] = setting[key]
  end
end
local function restored(setting)
  for _, key in ipairs({ "manage", "files_with_profile", "missing_profile", "working_rgb_space" }) do
    assert(app.preferences.color[key] == setting[key], "Color preference was not restored: " .. key)
  end
  for _, key in ipairs({ "rgbmap_algorithm", "fit_criteria", "dithering_algorithm" }) do
    assert(app.preferences.quantization[key] == setting[key], "Mapping preference changed: " .. key)
  end
  assert(
    app.activeSprite == sentinel
      and app.activeLayer == sentinel.layers[1]
      and app.activeFrame == sentinel.frames[2],
    "Active document state was not restored"
  )
  assert(app.fgColor == foreground and app.bgColor == background, "Active colors were not restored")
end
for number, setting in ipairs(settings) do
  install(setting)
  app.params.request = assert(app.params["request_" .. number])
  app.params.response = assert(app.params["response_" .. number])
  dofile(handler)
  restored(setting)
end
-- Exercise restoration on a bounded refusal as well as both successful invocations.
install(settings[1])
app.params.request = assert(app.params.refused_request)
app.params.response = assert(app.params.refused_response)
dofile(handler)
restored(settings[1])
sentinel:close()
