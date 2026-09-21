-- Shared fixed inspection semantics for packaged Sprite handlers.
local module = {}
local json_null = json.decode("null")

local function array(value)
  return value
end

local function rgba(color)
  return {
    red = color.red,
    green = color.green,
    blue = color.blue,
    alpha = color.alpha,
  }
end

local function rectangle(value)
  return { x=value.x, y=value.y, width=value.width, height=value.height }
end

local function point(value)
  return { x=value.x, y=value.y }
end

local function size(value)
  return { width=value.width, height=value.height }
end

local function color_mode(value)
  if value == ColorMode.RGB then return "rgb" end
  if value == ColorMode.GRAY then return "grayscale" end
  if value == ColorMode.INDEXED then return "indexed" end
  error("unsupported Sprite Color Mode")
end

local function blend_mode(value)
  local modes = {
    { BlendMode.NORMAL, "normal" },
    { BlendMode.MULTIPLY, "multiply" },
    { BlendMode.SCREEN, "screen" },
    { BlendMode.OVERLAY, "overlay" },
    { BlendMode.DARKEN, "darken" },
    { BlendMode.LIGHTEN, "lighten" },
    { BlendMode.COLOR_DODGE, "color_dodge" },
    { BlendMode.COLOR_BURN, "color_burn" },
    { BlendMode.HARD_LIGHT, "hard_light" },
    { BlendMode.SOFT_LIGHT, "soft_light" },
    { BlendMode.DIFFERENCE, "difference" },
    { BlendMode.EXCLUSION, "exclusion" },
    { BlendMode.HSL_HUE, "hsl_hue" },
    { BlendMode.HSL_SATURATION, "hsl_saturation" },
    { BlendMode.HSL_COLOR, "hsl_color" },
    { BlendMode.HSL_LUMINOSITY, "hsl_luminosity" },
    { BlendMode.ADDITION, "addition" },
    { BlendMode.SUBTRACT, "subtract" },
    { BlendMode.DIVIDE, "divide" },
  }
  for _, item in ipairs(modes) do
    if value == item[1] then return item[2] end
  end
  return "unknown_" .. tostring(value)
end

local function tag_direction(value)
  if value == AniDir.FORWARD then return "forward" end
  if value == AniDir.REVERSE then return "reverse" end
  if value == AniDir.PING_PONG then return "ping_pong" end
  if value == AniDir.PING_PONG_REVERSE then return "ping_pong_reverse" end
  return "unknown_" .. tostring(value)
end

local function background_color(layer)
  if not layer.isBackground or #layer.cels == 0 then return json_null end
  local pixel = layer.cels[1].image:getPixel(0, 0)
  return {
    red = app.pixelColor.rgbaR(pixel),
    green = app.pixelColor.rgbaG(pixel),
    blue = app.pixelColor.rgbaB(pixel),
    alpha = app.pixelColor.rgbaA(pixel),
  }
end

local function copy_path(path, index)
  local result = {}
  for i, value in ipairs(path) do result[i] = value end
  result[#result + 1] = index
  return result
end

local function inspect_layers(layers, parent_path, paths, counts)
  local result = {}
  for index = 1, #layers do
    local layer = layers[index]
    local path = copy_path(parent_path, index)
    paths[layer] = path
    counts.layers = counts.layers + 1
    local children = {}
    if layer.isGroup then
      children = inspect_layers(layer.layers, path, paths, counts)
    end
    result[#result + 1] = {
      path = path,
      name = layer.name,
      opacity = layer.opacity == nil and json_null or layer.opacity,
      blend_mode = layer.blendMode == nil and json_null or blend_mode(layer.blendMode),
      is_image = layer.isImage,
      is_group = layer.isGroup,
      is_tilemap = layer.isTilemap,
      is_reference = layer.isReference,
      is_visible = layer.isVisible,
      is_editable = layer.isEditable,
      is_continuous = layer.isContinuous,
      is_collapsed = layer.isCollapsed,
      is_transparent = layer.isTransparent,
      is_background = layer.isBackground,
      background_color = background_color(layer),
      children = array(children),
    }
  end
  return array(result)
end

local function requested_set(scope)
  local result = {}
  for index = 1, #scope do result[scope[index]] = true end
  return result
end

local function cel_layer_path(sprite, layer)
  local path = {}
  local current = layer
  while true do
    table.insert(path, 1, current.stackIndex)
    if current.parent == sprite then break end
    current = current.parent
  end
  return path
end

local function inspect_slice_keys(slice)
  local available, native_keys = pcall(function() return slice.keys end)
  if not available or native_keys == nil then return nil end
  local keys = {}
  for index = 1, #native_keys do
    local key = native_keys[index]
    local frame_number = key.frameNumber
    if frame_number == nil and key.frame ~= nil then
      frame_number = key.frame.frameNumber
    end
    assert(type(frame_number) == "number", "Slice Key has no Frame number")
    keys[#keys + 1] = {
      frame_number = frame_number,
      bounds = rectangle(key.bounds),
      center = key.center == nil and json_null or rectangle(key.center),
      pivot = key.pivot == nil and json_null or point(key.pivot),
    }
  end
  return array(keys)
end

function module.inspect(sprite, scope)
  local requested = requested_set(scope)
  local paths = {}
  local counts = { layers = 0 }
  local all_layers = inspect_layers(sprite.layers, {}, paths, counts)
  local result = {
    metadata = {
      width = sprite.width,
      height = sprite.height,
      color_mode = color_mode(sprite.colorMode),
      frame_count = #sprite.frames,
      tag_count = #sprite.tags,
      palette_count = #sprite.palettes,
      layer_count = counts.layers,
      cel_count = #sprite.cels,
      slice_count = #sprite.slices,
      tileset_count = #sprite.tilesets,
      transparent_color_index = sprite.transparentColor,
      grid_bounds = rectangle(sprite.gridBounds),
      pixel_ratio = size(sprite.pixelRatio),
    },
    frames = json_null,
    tags = json_null,
    palettes = json_null,
    layers = json_null,
    cels = json_null,
    slices = json_null,
    tilesets = json_null,
  }

  if requested.frames then
    local frames = {}
    for index = 1, #sprite.frames do
      local frame = sprite.frames[index]
      frames[#frames + 1] = {
        frame_number = frame.frameNumber,
        duration_ms = math.floor(frame.duration * 1000 + 0.5),
      }
    end
    result.frames = array(frames)
  end

  if requested.tags then
    local tags = {}
    for index = 1, #sprite.tags do
      local tag = sprite.tags[index]
      tags[#tags + 1] = {
        name = tag.name,
        from_frame = tag.fromFrame.frameNumber,
        to_frame = tag.toFrame.frameNumber,
        direction = tag_direction(tag.aniDir),
        repeats = tag.repeats,
        color = rgba(tag.color),
      }
    end
    result.tags = array(tags)
  end

  if requested.palettes then
    local palettes = {}
    for palette_index = 1, #sprite.palettes do
      local palette = sprite.palettes[palette_index]
      local entries = {}
      for index = 0, #palette - 1 do
        entries[#entries + 1] = { index=index, color=rgba(palette:getColor(index)) }
      end
      palettes[#palettes + 1] = {
        frame_number = palette.frame.frameNumber,
        entries = array(entries),
      }
    end
    result.palettes = array(palettes)
  end

  if requested.layers then result.layers = all_layers end

  if requested.cels then
    local cels = {}
    for index = 1, #sprite.cels do
      local cel = sprite.cels[index]
      cels[#cels + 1] = {
        layer_path = cel_layer_path(sprite, cel.layer),
        frame_number = cel.frameNumber,
        bounds = rectangle(cel.bounds),
        opacity = cel.opacity,
        z_index = cel.zIndex,
      }
    end
    result.cels = array(cels)
  end

  if requested.slices then
    if #sprite.slices == 0 then
      result.slices = array({})
    else
      local slices = {}
      local complete = true
      for index = 1, #sprite.slices do
        local slice = sprite.slices[index]
        local keys = inspect_slice_keys(slice)
        if keys == nil then
          complete = false
          break
        end
        slices[#slices + 1] = { name=slice.name, keys=keys }
      end
      -- Current public APIs expose only the effective value when `keys` is absent.
      result.slices = complete and array(slices) or json_null
    end
  end

  if requested.tilesets then
    local tilesets = {}
    for index = 1, #sprite.tilesets do
      local tileset = sprite.tilesets[index]
      tilesets[#tilesets + 1] = {
        name = tileset.name,
        tile_count = #tileset,
        base_index = tileset.baseIndex,
        grid_origin = point(tileset.grid.origin),
        tile_size = size(tileset.grid.tileSize),
      }
    end
    result.tilesets = array(tilesets)
  end

  return result
end

return module
