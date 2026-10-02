-- Shared Filter target resolution, typed Channels, and invocation-local state.
local module = {}
local json_null = json.decode("null")
local layers = dofile(app.params.layer_select)
local selection = dofile(app.params.selection_mask)
local digest = dofile(app.params.digest)
local inspection = dofile(app.params.inspection)
local persistence = dofile(app.params.persistence)
local image_uses = dofile(app.params.palette_images)

function module.snapshot(sprite, uuids, omit_palettes)
  local sections = { "frames", "tags", "layers", "cels", "slices", "tilesets" }
  if not omit_palettes then sections[#sections + 1] = "palettes" end
  return {
    document = persistence.snapshot(sprite, inspection, digest, sections, uuids),
    images = image_uses.facts(image_uses.resolve(sprite)),
    tiles = image_uses.tile_metadata(sprite),
    tilemaps = dofile(app.params.filter_tiles).snapshot(sprite, "persisted"),
  }
end

function module.reject(reason, unsupported)
  return {
    rejection = {
      code = unsupported and "filter_unsupported_document" or "filter_invalid_target",
      message = reason,
      details = { reason = reason },
    },
  }
end

local function editable(sprite, layer)
  if layer.isGroup then return false end
  while layer ~= sprite do
    if not layer.isVisible or not layer.isEditable or layer.isReference then return false end
    layer = layer.parent
  end
  return true
end

function module.targets(sprite, target, uuids, color_mode, allow_tilemaps)
  local chosen, frames, excluded = {}, {}, {}
  if target.kind == "selected" then
    local seen = {}
    for _, address in ipairs(target.layers) do
      local resolved, _, message = layers.resolve(sprite, address, uuids)
      if not resolved then return nil, module.reject(message) end
      local layer = resolved.layer
      local path = table.concat(resolved.path, "/")
      if seen[path] then
        return nil, module.reject("Filter Layer addresses resolve to the same Layer")
      end
      seen[path] = true
      if not editable(sprite, layer) then
        return nil, module.reject("Selected Layer cannot edit pixels")
      end
      chosen[#chosen + 1] = layer
    end
    for _, number in ipairs(target.frame_numbers) do
      if number > #sprite.frames then
        return nil, module.reject("Filter Frame is outside the timeline")
      end
      frames[#frames + 1] = math.tointeger(number)
    end
  else
    local function visit(siblings)
      for _, layer in ipairs(siblings) do
        if editable(sprite, layer) then
          chosen[#chosen + 1] = layer
        else
          excluded[#excluded + 1] =
            { layer_path = layers.current_path(sprite, layer), reason = "cannot-edit-pixels" }
        end
        if layer.isGroup then visit(layer.layers) end
      end
    end
    visit(sprite.layers)
    for number = 1, #sprite.frames do
      frames[#frames + 1] = number
    end
  end
  local intersections, existing, images, image_numbers = {}, {}, {}, {}
  for _, layer in ipairs(chosen) do
    for _, frame in ipairs(frames) do
      local cel = layer:cel(frame)
      local number = nil
      if cel then
        if layer.isTilemap and not allow_tilemaps then
          return nil, module.reject("Tilemap pixel filtering is not supported by this Filter", true)
        end
        number = image_numbers[cel.image.id]
        if not number then
          number = #images + 1
          image_numbers[cel.image.id] = number
          local mode = layer.isTilemap and "tilemap" or color_mode
          images[number] = {
            layer = layer,
            frame = frame,
            image_kind = layer.isTilemap and "tilemap-placement" or "ordinary",
            mode = mode,
            before = digest.image_content(cel.image, mode),
          }
        elseif images[number].layer == layer and frame < images[number].frame then
          -- Native selected Frames are ordered, even when the request is not.
          -- A linked Image is filtered at its earliest selected Cel position.
          images[number].frame = frame
        end
      end
      local fact = {
        layer_path = layers.current_path(sprite, layer),
        frame_number = frame,
        image_number = number or json_null,
      }
      intersections[#intersections + 1] = fact
      if cel then existing[#existing + 1] = fact end
    end
  end
  if #images == 0 then return nil, module.reject("Filter Cels Target contains no existing Cels") end
  local affected, cel_states = {}, {}
  for _, cel in ipairs(sprite.cels) do
    local number = image_numbers[cel.image.id]
    if number then
      cel_states[#cel_states + 1] = {
        layer = cel.layer,
        frame = cel.frameNumber,
        before = selection.rectangle(cel.bounds),
      }
      affected[#affected + 1] = {
        layer_path = layers.current_path(sprite, cel.layer),
        frame_number = cel.frame.frameNumber,
        image_number = number,
      }
    end
  end
  return {
    layers = chosen,
    frames = frames,
    images = images,
    requested_intersections = intersections,
    existing_target_cels = existing,
    excluded_layers = excluded,
    affected_cels = affected,
    cel_states = cel_states,
  }
end

function module.channels(channels)
  if channels.kind == "index" then return FilterChannels.INDEX, { kind = "index" } end
  local flags, names = 0, {}
  local mapping = {
    red = FilterChannels.RED,
    green = FilterChannels.GREEN,
    blue = FilterChannels.BLUE,
    gray = FilterChannels.GRAY,
    alpha = FilterChannels.ALPHA,
  }
  local wanted = {}
  for _, name in ipairs(channels.names) do
    wanted[name] = true
  end
  for _, name in ipairs({ "red", "green", "blue", "gray", "alpha" }) do
    if wanted[name] then
      flags = flags | mapping[name]
      names[#names + 1] = name
    end
  end
  return flags, { kind = "components", names = names }
end

function module.pixel_selection(sprite, requested)
  local canvas = Rectangle(0, 0, sprite.width, sprite.height)
  if not requested then
    return Selection(canvas), { kind = "all", rectangle = selection.rectangle(canvas) }
  end
  local mask = selection.materialize(requested)
  mask:intersect(canvas)
  local value = selection.encode(mask).selection
  if mask.isEmpty then
    -- A native empty Selection means no mask. Keep its bitmap active with two
    -- off-canvas pixels: bounds intersect the Canvas, but no Canvas pixel is set.
    -- A wholly off-canvas rectangle instead makes Filter initialization fail.
    mask = Selection(Rectangle(-1, 0, 1, 1))
    mask:add(Rectangle(sprite.width, 0, 1, 1))
  end
  return mask, value
end

function module.with_state(sprite, operation)
  local previous = {
    sprite = app.activeSprite,
    layer = app.activeLayer,
    frame = app.activeFrame,
    layers = {},
    frames = {},
    colors = app.range.colors,
    empty = app.range.isEmpty,
  }
  -- Range getters return userdata collections; setters accept plain Lua arrays.
  for _, layer in ipairs(app.range.layers) do
    previous.layers[#previous.layers + 1] = layer
  end
  for _, frame in ipairs(app.range.frames) do
    previous.frames[#previous.frames + 1] = frame
  end
  local mask = selection.copy(sprite.selection)
  local ok, result = pcall(operation)
  local restored, problem = pcall(function()
    sprite.selection = mask
    if previous.sprite and previous.sprite.isValid then
      app.activeSprite = previous.sprite
      app.activeLayer = previous.layer
      app.activeFrame = previous.frame
    end
    app.range:clear()
    if not previous.empty then
      app.range.layers = previous.layers
      app.range.frames = previous.frames
    end
    app.range.colors = previous.colors
  end)
  assert(restored, problem)
  if not ok then error(result, 0) end
  return result
end

return module
