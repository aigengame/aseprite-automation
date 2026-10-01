-- Native Color Quantization and Palette publication checks.
local module = {}
local palettes = dofile(app.params.palette)
local effective = dofile(app.params.effective_palette)
local images = dofile(app.params.palette_images)
local transforms = dofile(app.params.palette_transform)
local persistence = dofile(app.params.persistence)

local function missing_change(payload, frame_count)
  return {
    rejection = {
      code = "palette_change_missing",
      message = "Color Quantization requires an exact existing Palette Change",
      details = {
        palette_frame_number = payload.palette_frame_number,
        frame_count = frame_count,
      },
    },
  }
end

local function reject(
  reason,
  frame,
  original_size,
  candidate_size,
  original_mask,
  candidate_mask,
  use
)
  local details = {
    palette_frame_number = frame,
    reason = reason,
    original_palette_size = original_size,
    candidate_palette_size = candidate_size,
    cel_uses = use and use.cel_uses or {},
    tile_uses = use and use.tile_uses or {},
  }
  if original_mask ~= nil then
    details.original_transparent_color = original_mask
    details.candidate_transparent_color = candidate_mask
  end
  if use ~= nil then details.index = use.index end
  return {
    rejection = {
      code = "palette_quantization_rejected",
      message = "Generated Palette would invalidate Indexed Sprite data",
      details = details,
    },
  }
end

local function selected_change(sprite, payload)
  local raw = payload.palette_frame_number
  assert(type(raw) == "string" and raw:match("^[1-9]%d*$"), "invalid Palette Change Frame")
  local frame = tonumber(raw)
  if frame == nil or frame > #sprite.frames then return nil end
  local selected, owner = effective.resolve(sprite, frame)
  if selected == nil or owner ~= frame then return nil end
  return selected, frame
end

function module.generate(sprite, payload)
  local selected, frame = selected_change(sprite, payload)
  if selected == nil then return missing_change(payload, #sprite.frames) end
  local max_colors = tonumber(payload.max_colors)
  assert(max_colors and max_colors % 1 == 0 and max_colors >= 1 and max_colors <= 256)
  assert(type(payload.with_alpha) == "boolean", "with_alpha is required")
  assert(
    type(payload.new_layer_blending_method) == "boolean",
    "new_layer_blending_method is required"
  )
  local algorithm = payload.rgb_map_algorithm
  assert(algorithm == "default" or algorithm == "rgb5a3" or algorithm == "octree")

  local old_mask = sprite.colorMode == ColorMode.INDEXED and sprite.transparentColor or nil
  local original_size = #selected
  local previous = {
    sprite = app.activeSprite,
    frame = app.activeFrame,
    layer = app.activeLayer,
    picks = app.range.colors,
    blend = app.preferences.experimental.new_blend,
  }
  local ok, err = pcall(function()
    app.activeSprite = sprite
    app.activeFrame = sprite.frames[frame]
    app.range.colors = {}
    app.preferences.experimental.new_blend = payload.new_layer_blending_method
    app.command.ColorQuantization {
      ui = false,
      withAlpha = payload.with_alpha,
      maxColors = max_colors,
      useRange = false,
      algorithm = algorithm,
    }
  end)
  -- Restore even when the native command or an editor setter throws.
  local restored_blend = pcall(
    function() app.preferences.experimental.new_blend = previous.blend end
  )
  local restored_picks = pcall(function() app.range.colors = previous.picks end)
  local restored_context = true
  if previous.sprite ~= nil and previous.sprite.isValid then
    restored_context = pcall(function() app.activeSprite = previous.sprite end)
    if previous.layer ~= nil then
      restored_context = pcall(function() app.activeLayer = previous.layer end) and restored_context
    end
    if previous.frame ~= nil then
      restored_context = pcall(function() app.activeFrame = previous.frame end) and restored_context
    end
  end
  if not ok then error(err) end
  assert(
    restored_blend and restored_picks and restored_context,
    "Color Quantization could not restore editor state"
  )

  local current = palettes.get(sprite, frame)
  assert(current.rejection == nil, "Color Quantization removed its Palette Change")
  local change = current.palette
  local rendered, affected = {}, {}
  for number = 1, #sprite.frames do
    rendered[#rendered + 1] = number
  end
  for number = change.effective_frame_range.from_frame, change.effective_frame_range.to_frame do
    affected[#affected + 1] = number
  end
  local facts = {
    rendered_frames = rendered,
    affected_frames = affected,
    requested_max_colors = max_colors,
    actual_colors = #change.entries,
    with_alpha = payload.with_alpha,
    rgb_map_algorithm = algorithm,
    effective_rgb_map_algorithm = algorithm == "default" and "octree" or algorithm,
    new_layer_blending_method = payload.new_layer_blending_method,
  }
  if old_mask ~= nil then
    facts.original_transparent_color = old_mask
    facts.final_transparent_color = sprite.transparentColor
  end
  local result = palettes.list(sprite)
  result.palette = change
  result.quantization = facts
  return result, original_size
end

function module.apply(sprite, payload, uuids)
  local before = transforms.snapshot(sprite, uuids)
  local original_mask = sprite.colorMode == ColorMode.INDEXED and sprite.transparentColor or nil
  local generated, original_size = module.generate(sprite, payload)
  if generated.rejection then return generated end
  local change = generated.palette
  local candidate_size = #change.entries
  local candidate_mask = sprite.colorMode == ColorMode.INDEXED and sprite.transparentColor or nil
  if original_mask ~= nil then
    if candidate_mask ~= original_mask then
      return reject(
        "transparent_index_changed",
        change.palette_frame_number,
        original_size,
        candidate_size,
        original_mask,
        candidate_mask
      )
    end
    local invalid = images.invalid_palette_use(sprite, change)
    if invalid ~= nil then
      return reject(
        invalid.reason,
        invalid.palette_frame_number,
        original_size,
        candidate_size,
        original_mask,
        candidate_mask,
        invalid
      )
    end
  end
  local after = transforms.snapshot(sprite, uuids)
  for _, candidate in ipairs(after.document.sprite.palettes) do
    if candidate.frame_number == change.palette_frame_number then
      for _, expected in ipairs(before.document.sprite.palettes) do
        if expected.frame_number == candidate.frame_number then
          expected.entries = candidate.entries
          break
        end
      end
      break
    end
  end
  persistence.assert_equal(before, after, "Color Quantization")
  return generated
end

return module
