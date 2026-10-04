-- Native Export Image semantics shared by the handler and capability probe.
local module = {}
-- Aseprite's ColorProfileBehavior values (data/pref.xml): DISABLE=0, EMBEDDED=1.
local profile_disable = 0
local profile_embedded = 1

local profile_file = dofile(app.params.color_profile_file)

local function source_profile(sprite)
  local color_space = sprite.colorSpace
  assert(color_space ~= nil, "Source Sprite has no Color Profile observation")
  if color_space == ColorSpace() then return "none" end
  if color_space == ColorSpace { sRGB = true } then return "srgb" end
  error("unsupported Source Sprite Color Profile")
end

local function reject_tilemap_images(layers, frame_number)
  for _, layer in ipairs(layers) do
    if layer.isGroup then
      reject_tilemap_images(layer.layers, frame_number)
    elseif layer.isTilemap and layer:cel(frame_number) ~= nil then
      error("unsupported Tilemap Image")
    end
  end
end

function module.with_source(source_file, frame_numbers, run)
  local previous_manage = app.preferences.color.manage
  local previous_files_with_profile = app.preferences.color.files_with_profile
  local previous_missing_profile = app.preferences.color.missing_profile
  local previous_compose_groups = app.preferences.experimental.compose_groups
  local source = nil
  local ok, result = pcall(function()
    local declared = profile_file.declared_profile(source_file)
    assert(declared == "none" or declared == "srgb", "unsupported Source Sprite Color Profile")
    app.preferences.color.manage = true
    app.preferences.color.files_with_profile = profile_embedded
    app.preferences.color.missing_profile = profile_disable
    app.preferences.experimental.compose_groups = true
    source = assert(app.open(source_file), "could not open Source Sprite")
    assert(source.colorMode == ColorMode.RGB, "unsupported Source Color Mode")
    for _, number in ipairs(frame_numbers) do
      assert(number >= 1 and number <= #source.frames, "Frame Number is outside the Source Sprite")
      reject_tilemap_images(source.layers, number)
    end
    if declared == "none" then source:assignColorSpace(ColorSpace()) end
    local profile = source_profile(source)
    assert(profile == declared, "loaded Sprite Color Profile differs from file")
    return run(source, profile)
  end)
  if source ~= nil then pcall(function() source:close() end) end
  pcall(function() app.preferences.color.manage = previous_manage end)
  pcall(function() app.preferences.color.files_with_profile = previous_files_with_profile end)
  pcall(function() app.preferences.color.missing_profile = previous_missing_profile end)
  pcall(function() app.preferences.experimental.compose_groups = previous_compose_groups end)
  if not ok then error(result) end
  return result
end

function module.render_frame(source, frame_number)
  local rendered = Image(source.spec)
  rendered:drawSprite(source, frame_number, 0, 0)
  assert(rendered.colorMode == ColorMode.RGB, "renderer changed Color Mode")
  assert(
    rendered.bytesPerPixel == 4 and rendered.rowStride == source.width * 4,
    "unexpected native RGB Image layout"
  )
  return rendered
end

-- Encode the supplied native Image; callers own format/profile policy and verification.
function module.encode_image(image, path, palette)
  local saved
  if palette ~= nil then
    saved = image:saveAs { filename = path, palette = palette }
  else
    saved = image:saveAs(path)
  end
  assert(saved, "native PNG encoding failed")
end

function module.execute(payload)
  assert(type(payload.source_sprite_file) == "string", "missing Source Sprite File")
  assert(type(payload.staged_png_file) == "string", "missing staged PNG file")
  assert(type(payload.staged_rgba_file) == "string", "missing staged RGBA file")
  assert(type(payload.frame_number) == "number", "missing Frame Number")
  assert(payload.color_mode == "preserve", "unsupported Color Mode behavior")
  assert(payload.color_profile == "preserve", "unsupported Color Profile behavior")
  assert(payload.transparency == "preserve", "unsupported transparency behavior")

  return module.with_source(
    payload.source_sprite_file,
    { payload.frame_number },
    function(source, profile)
      local rendered = module.render_frame(source, payload.frame_number)
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
        rendered_byte_size = #bytes,
      }
      local rendered_file = assert(io.open(payload.staged_rgba_file, "wb"))
      assert(rendered_file:write(bytes))
      assert(rendered_file:close())
      module.encode_image(rendered, payload.staged_png_file)
      return facts
    end
  )
end

return module
