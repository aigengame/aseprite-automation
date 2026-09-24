-- Shared fixed inspection semantics for packaged Sprite handlers.
local module = {}
local json_null = json.decode("null")

local function rgba(color)
  return {
    red = color.red,
    green = color.green,
    blue = color.blue,
    alpha = color.alpha,
  }
end

local function rectangle(value)
  return { x = value.x, y = value.y, width = value.width, height = value.height }
end

local function point(value) return { x = value.x, y = value.y } end

local function size(value) return { width = value.width, height = value.height } end

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
  error("unsupported Tag Animation Direction")
end

local function copy_path(path, index)
  local result = {}
  for i, value in ipairs(path) do
    result[i] = value
  end
  result[#result + 1] = index
  return result
end

local function inspect_layers(layers, parent_path, paths, counts, persist_uuids)
  local result = {}
  for index = 1, #layers do
    local layer = layers[index]
    local path = copy_path(parent_path, index)
    paths[layer] = path
    counts.layers = counts.layers + 1
    local children = {}
    if layer.isGroup then
      children = inspect_layers(layer.layers, path, paths, counts, persist_uuids)
    end
    result[#result + 1] = {
      path = path,
      name = layer.name,
      layer_uuid = persist_uuids and tostring(layer.uuid) or json_null,
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
      children = children,
    }
  end
  return result
end

local function requested_set(scope)
  local result = {}
  for index = 1, #scope do
    result[scope[index]] = true
  end
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

local function read_file(path)
  local file = assert(io.open(path, "rb"), "could not open Slice vendor data")
  local payload = file:read("*a")
  file:close()
  return payload
end

local function is_json_object(value)
  local kind = type(value)
  return kind == "table" or kind == "userdata"
end

local function vendor_rectangle(value)
  assert(is_json_object(value), "Slice Key Rectangle is not an object")
  assert(
    type(value.x) == "number" and type(value.y) == "number",
    "Slice Key Rectangle has invalid coordinates"
  )
  assert(
    type(value.w) == "number" and type(value.h) == "number",
    "Slice Key Rectangle has invalid dimensions"
  )
  return { x = value.x, y = value.y, width = value.w, height = value.h }
end

local function vendor_point(value)
  assert(is_json_object(value), "Slice Key Point is not an object")
  assert(
    type(value.x) == "number" and type(value.y) == "number",
    "Slice Key Point has invalid coordinates"
  )
  return { x = value.x, y = value.y }
end

local function restore_editor_state(previous)
  if previous.sprite ~= nil and previous.sprite.isValid then
    pcall(function() app.activeSprite = previous.sprite end)
    pcall(function() app.activeLayer = previous.layer end)
    pcall(function() app.activeFrame = previous.frame end)
  end
end

local function inspect_slices(sprite)
  if #sprite.slices == 0 then return {} end
  local workspace = assert(app.params.workspace, "missing Kernel workspace")
  local data_path = workspace .. "/sprite-slices.json"
  local texture_path = workspace .. "/sprite-slices.png"
  local previous = {
    sprite = app.activeSprite,
    layer = app.activeLayer,
    frame = app.activeFrame,
  }
  local exported, failure = pcall(function()
    app.activeSprite = sprite
    app.command.ExportSpriteSheet {
      ui = false,
      recent = false,
      askOverwrite = false,
      type = SpriteSheetType.HORIZONTAL,
      textureFilename = texture_path,
      dataFilename = data_path,
      dataFormat = SpriteSheetDataFormat.JSON_HASH,
      listLayers = false,
      listTags = false,
      listSlices = true,
      openGenerated = false,
    }
  end)
  restore_editor_state(previous)
  if not exported then error(failure) end

  local vendor = json.decode(read_file(data_path))
  assert(
    is_json_object(vendor) and is_json_object(vendor.meta),
    "Slice vendor data has no metadata object"
  )
  local vendor_slices = vendor.meta.slices
  assert(is_json_object(vendor_slices), "Slice vendor data has no Slice array")
  assert(#vendor_slices == #sprite.slices, "Slice vendor count differs from the opened Sprite")

  local slices = {}
  for slice_index = 1, #sprite.slices do
    local native_slice = sprite.slices[slice_index]
    local vendor_slice = vendor_slices[slice_index]
    assert(is_json_object(vendor_slice), "Slice vendor entry is not an object")
    assert(
      vendor_slice.name == native_slice.name,
      "Slice vendor order differs from the opened Sprite"
    )
    assert(type(native_slice.data) == "string", "Slice user data is not a string")
    assert(is_json_object(vendor_slice.keys), "Slice vendor entry has no Keys")
    local keys = {}
    for key_index = 1, #vendor_slice.keys do
      local key = vendor_slice.keys[key_index]
      assert(is_json_object(key), "Slice Key vendor entry is not an object")
      assert(
        type(key.frame) == "number"
          and key.frame >= 0
          and key.frame < #sprite.frames
          and key.frame % 1 == 0,
        "Slice Key has an invalid Frame"
      )
      keys[#keys + 1] = {
        frame_number = key.frame + 1,
        bounds = vendor_rectangle(key.bounds),
        center = key.center == nil and json_null or vendor_rectangle(key.center),
        pivot = key.pivot == nil and json_null or vendor_point(key.pivot),
      }
    end
    assert(#keys > 0, "Slice vendor entry has no explicit Keys")
    slices[#slices + 1] = {
      name = native_slice.name,
      data = native_slice.data,
      keys = keys,
    }
  end
  return slices
end

function module.inspect(sprite, scope)
  local requested = requested_set(scope)
  local paths = {}
  local counts = { layers = 0 }
  local all_layers = inspect_layers(sprite.layers, {}, paths, counts, sprite.useLayerUuids)
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
      use_layer_uuids = sprite.useLayerUuids,
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
    result.frames = frames
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
    result.tags = tags
  end

  if requested.palettes then
    local palettes = {}
    for palette_index = 1, #sprite.palettes do
      local palette = sprite.palettes[palette_index]
      local entries = {}
      for index = 0, #palette - 1 do
        entries[#entries + 1] = { index = index, color = rgba(palette:getColor(index)) }
      end
      palettes[#palettes + 1] = {
        frame_number = palette.frame.frameNumber,
        entries = entries,
      }
    end
    result.palettes = palettes
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
    result.cels = cels
  end

  if requested.slices then result.slices = inspect_slices(sprite) end

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
    result.tilesets = tilesets
  end

  return result
end

return module
