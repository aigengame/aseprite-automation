-- Native Aseprite owns classification, neighborhood sampling and writeback.
local module = {}
local application = dofile(app.params.filter_application)
local support = dofile(app.params.filter_support)
local colors = dofile(app.params.raster_color)

local function matrix(value)
  if value.kind == "preset" then return value.name end
  -- Neighbor traversal starts at the top-left with bit 1, not the editor UI's
  -- reversed display order. The unused center bit is never exposed.
  local bits = {
    ["top-left"] = 1,
    top = 2,
    ["top-right"] = 4,
    left = 8,
    right = 32,
    ["bottom-left"] = 64,
    bottom = 128,
    ["bottom-right"] = 256,
  }
  local mask = 0
  for _, name in ipairs(value.neighbors) do
    mask = mask | assert(bits[name])
  end
  return mask
end

local function color(value)
  if value.kind == "rgba" then
    return Color { r = value.red, g = value.green, b = value.blue, a = value.alpha }
  elseif value.kind == "grayscale" then
    return Color { gray = value.gray, alpha = value.alpha }
  end
  return Color { index = value.index }
end

function module.apply(sprite, payload, uuids)
  if payload.color_mode == "indexed" and payload.channels.kind == "components" then
    return support.reject(
      "Indexed component Outline is unavailable (native baseline 1.3.18.5)",
      true
    )
  end
  local result = application.apply(
    sprite,
    payload,
    uuids,
    "Outline",
    function(flags)
      assert(
        app.command.Outline {
          ui = false,
          channels = flags,
          place = payload.place,
          matrix = matrix(payload.matrix),
          color = color(payload.outline_color),
          bgColor = color(payload.background_color),
          tiledMode = payload.tiled_mode,
        },
        "Native Outline failed"
      )
      return true
    end,
    nil,
    function(targets, basis)
      if
        payload.color_mode == "indexed"
        and (
          payload.outline_color.index >= basis.palette_size
          or payload.background_color.index >= basis.palette_size
        )
      then
        return support.reject("Outline Color Index is outside the declared Effective Palette")
      end
      if payload.color_mode ~= "indexed" then
        -- Outline projects both colors through the active Layer once. Prefer
        -- a selected transparent Layer for mixed targets; Background-only keeps
        -- native opaque projection, independent of caller target ordering.
        for _, image in ipairs(targets.images) do
          if not image.layer.isBackground then
            app.activeCel = image.layer:cel(image.frame)
            break
          end
        end
      end
    end
  )
  if not result.rejection then
    result.application = nil
    result.palette_indexes = nil
    result.place = payload.place
    if payload.matrix.kind == "preset" then
      result.matrix = { kind = "preset", name = payload.matrix.name }
    else
      local neighbors = {}
      for _, name in ipairs(payload.matrix.neighbors) do
        neighbors[#neighbors + 1] = name
      end
      result.matrix = { kind = "custom", neighbors = neighbors }
    end
    result.tiled_mode = payload.tiled_mode
    result.outline_color = colors.copy_color(payload.outline_color)
    result.background_color = colors.copy_color(payload.background_color)
  end
  return result
end

return module
