-- Native Export Image semantics shared by the handler and capability probe.
local module = {}

local function source_profile(sprite)
  local color_space = sprite.colorSpace
  assert(color_space ~= nil, "Source Sprite has no Color Profile observation")
  if color_space == ColorSpace() then return "none" end
  if color_space == ColorSpace{ sRGB=true } then return "srgb" end
  error("unsupported Source Sprite Color Profile")
end

function module.execute(payload, digest)
  assert(type(payload.source_sprite_file) == "string", "missing Source Sprite File")
  assert(type(payload.staged_png_file) == "string", "missing staged PNG file")
  assert(type(payload.frame_number) == "number", "missing Frame Number")
  assert(payload.color_mode == "preserve", "unsupported Color Mode behavior")
  assert(payload.color_profile == "preserve", "unsupported Color Profile behavior")
  assert(payload.transparency == "preserve", "unsupported transparency behavior")

  local previous_manage = app.preferences.color.manage
  local previous_compose_groups = app.preferences.experimental.compose_groups
  local source = nil
  local ok, result = pcall(function()
    app.preferences.color.manage = true
    app.preferences.experimental.compose_groups = true
    source = assert(app.open(payload.source_sprite_file), "could not open Source Sprite")
    assert(source.colorMode == ColorMode.RGB, "unsupported Source Color Mode")
    assert(payload.frame_number >= 1 and payload.frame_number <= #source.frames,
           "Frame Number is outside the Source Sprite")
    local profile = source_profile(source)
    local rendered = Image(source.spec)
    rendered:drawSprite(source, payload.frame_number, 0, 0)
    assert(rendered.colorMode == ColorMode.RGB, "renderer changed Color Mode")
    assert(rendered.bytesPerPixel == 4 and rendered.rowStride == source.width * 4,
           "unexpected native RGB Image layout")
    local bytes = rendered.bytes
    local alpha_min, alpha_max = 255, 0
    for offset = 4, #bytes, 4 do
      local alpha = string.byte(bytes, offset)
      if alpha < alpha_min then alpha_min = alpha end
      if alpha > alpha_max then alpha_max = alpha end
    end
    local facts = {
      frame_number = payload.frame_number,
      width = source.width,
      height = source.height,
      color_mode = "rgb",
      color_profile = profile,
      alpha_min = alpha_min,
      alpha_max = alpha_max,
      content_digest = digest.fnv1a64(bytes),
    }
    assert(rendered:saveAs(payload.staged_png_file), "native PNG encoding failed")
    return facts
  end)
  if source ~= nil then pcall(function() source:close() end) end
  pcall(function() app.preferences.color.manage = previous_manage end)
  pcall(function() app.preferences.experimental.compose_groups = previous_compose_groups end)
  if not ok then error(result) end
  return result
end

return module
