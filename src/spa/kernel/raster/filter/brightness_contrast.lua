-- Aseprite owns percentage conversion, channel math, quantization, and clamping.
local module = {}
local support = dofile(app.params.filter_support)
local digest = dofile(app.params.digest)
local selection = dofile(app.params.selection_mask)

function module.apply(sprite, payload, uuids)
  local application = payload.application
  local mode = application.color_mode
  local modes = { rgb = ColorMode.RGB, grayscale = ColorMode.GRAY }
  if sprite.colorMode ~= modes[mode] then
    return support.reject("Source Color Mode differs from application", true)
  end
  local targets, rejection = support.targets(sprite, application.cels_target, uuids, mode)
  if rejection then return rejection end
  local flags, channels = support.channels(application.channels)
  return support.with_state(sprite, function()
    app.activeSprite = sprite
    app.activeCel = targets.images[1].cel
    app.range:clear()
    app.range.layers = targets.layers
    app.range.frames = targets.frames
    app.range.colors = {}
    sprite.selection = application.selection and selection.materialize(application.selection)
      or Selection(Rectangle(0, 0, sprite.width, sprite.height))
    app.transaction(
      "Brightness/Contrast",
      function()
        app.command.BrightnessContrast {
          ui = false,
          channels = flags,
          brightness = payload.brightness,
          contrast = payload.contrast,
        }
      end
    )
    local images, changed = {}, false
    for number, image in ipairs(targets.images) do
      local after = digest.image_content(image.cel.image, mode)
      local differs = image.before.value ~= after.value
      changed = changed or differs
      images[#images + 1] = {
        image_number = number,
        before_content_digest = image.before,
        after_content_digest = after,
        changed = differs,
      }
    end
    return {
      color_mode = mode,
      channels = channels,
      images = images,
      changed = changed,
      requested_intersections = targets.requested_intersections,
      existing_target_cels = targets.existing_target_cels,
      excluded_layers = targets.excluded_layers,
      affected_cels = targets.affected_cels,
    }
  end)
end

return module
