-- Native Replace Color owns matching, tolerance, and Indexed quantization.
local module = {}
local application = dofile(app.params.filter_application)
local effective = dofile(app.params.effective_palette)
local support = dofile(app.params.filter_support)

local function native_color(value)
  if value.kind == "rgba" then
    return Color { r = value.red, g = value.green, b = value.blue, a = value.alpha },
      {
        kind = "rgba",
        red = value.red,
        green = value.green,
        blue = value.blue,
        alpha = value.alpha,
      }
  elseif value.kind == "grayscale" then
    return Color { gray = value.gray, alpha = value.alpha },
      { kind = "grayscale", gray = value.gray, alpha = value.alpha }
  end
  return Color { index = value.index }, { kind = "palette-index", index = value.index }
end

local function changed_pixels(originals, transparent)
  local count = 0
  for _, original in ipairs(originals) do
    local cel = original.layer:cel(original.frame)
    local image = cel and cel.image
    for pixel in original.image:pixels() do
      local x = pixel.x + original.x - (cel and cel.position.x or 0)
      local y = pixel.y + original.y - (cel and cel.position.y or 0)
      local after = transparent
      if image and x >= 0 and y >= 0 and x < image.width and y < image.height then
        after = image:getPixel(x, y)
      end
      if pixel() ~= after then count = count + 1 end
    end
  end
  return count
end

function module.apply(sprite, payload, uuids)
  if payload.color_mode == "indexed" then
    if sprite.colorMode ~= ColorMode.INDEXED then
      return support.reject("Source Color Mode differs from application", true)
    end
    local frame = payload.palette_frame_number
    if frame > #sprite.frames then
      return support.reject("Palette Frame is outside the timeline")
    end
    local palette = effective.resolve(sprite, frame)
    if payload.from.index >= #palette or payload.to.index >= #palette then
      return support.reject("Replace Color input Index is outside the Effective Palette")
    end
  end
  local from, from_fact = native_color(payload.from)
  local to, to_fact = native_color(payload.to)
  local originals = {}
  local result = application.apply_pixels(
    sprite,
    payload,
    uuids,
    "Replace Color",
    function(flags, targets)
      for _, target in ipairs(targets.images) do
        local cel = target.layer:cel(target.frame)
        originals[#originals + 1] = {
          layer = target.layer,
          frame = target.frame,
          image = Image(cel.image),
          x = cel.position.x,
          y = cel.position.y,
        }
      end
      assert(
        app.command.ReplaceColor {
          ui = false,
          channels = flags,
          from = from,
          to = to,
          tolerance = payload.tolerance,
        },
        "Native Replace Color failed"
      )
      return true
    end
  )
  if not result.rejection then
    result.from, result.to, result.tolerance = from_fact, to_fact, payload.tolerance
    result.changed_pixel_count = changed_pixels(
      originals,
      sprite.colorMode == ColorMode.INDEXED and sprite.transparentColor or 0
    )
  end
  return result
end

return module
