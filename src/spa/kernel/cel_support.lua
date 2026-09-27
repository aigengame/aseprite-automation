-- Cel-owned inspection and lifecycle semantics over exact Layer/Frame addresses.
local module = {}
local json_null = json.decode("null")

local function rejection(code, message) return { rejection = { code = code, message = message } } end

local function path_copy(path)
  local result = {}
  for index, value in ipairs(path) do
    result[index] = value
  end
  return result
end

local function layer_path(sprite, layer)
  local path = {}
  local current = layer
  while current ~= sprite do
    table.insert(path, 1, current.stackIndex)
    current = current.parent
  end
  return path
end

local function is_regular_transparent(layer)
  return layer.isImage
    and layer.isTransparent
    and not layer.isGroup
    and not layer.isReference
    and not layer.isTilemap
    and not layer.isBackground
end
module.is_regular_transparent = is_regular_transparent

function module.sort_states(states)
  table.sort(states, function(left, right)
    if left.frame_number ~= right.frame_number then
      return left.frame_number < right.frame_number
    end
    for index = 1, math.min(#left.layer_path, #right.layer_path) do
      if left.layer_path[index] ~= right.layer_path[index] then
        return left.layer_path[index] < right.layer_path[index]
      end
    end
    return #left.layer_path < #right.layer_path
  end)
end

function module.inspect(sprite, layer, path, frame_number)
  local cel = layer.isImage and layer:cel(frame_number) or nil
  local fact = {
    layer_path = path_copy(path),
    frame_number = frame_number,
    exists = cel ~= nil,
    content = cel == nil and "absent" or cel.image:isEmpty() and "transparent" or "nonempty",
    is_background = layer.isBackground,
    is_tilemap = layer.isTilemap,
    position = json_null,
    image_bounds = json_null,
    opacity = json_null,
    z_index = json_null,
    linked_cels = {},
  }
  if cel == nil then return fact end
  fact.position = { x = cel.position.x, y = cel.position.y }
  if not layer.isTilemap then
    fact.image_bounds = {
      x = cel.bounds.x,
      y = cel.bounds.y,
      width = cel.image.width,
      height = cel.image.height,
    }
  end
  fact.opacity = cel.opacity
  fact.z_index = cel.zIndex
  for _, other in ipairs(sprite.cels) do
    if other ~= cel and other.image == cel.image then
      fact.linked_cels[#fact.linked_cels + 1] = {
        layer_path = layer_path(sprite, other.layer),
        frame_number = other.frameNumber,
      }
    end
  end
  return fact
end

function module.affected(sprite, image)
  local result = {}
  for _, current in ipairs(sprite.cels) do
    if current.image == image then
      result[#result + 1] = module.inspect(
        sprite,
        current.layer,
        layer_path(sprite, current.layer),
        current.frameNumber
      )
    end
  end
  module.sort_states(result)
  return result
end

function module.resolve(sprite, address, selection, verified_uuids)
  local selected, code, message = selection.resolve(sprite, address.layer, verified_uuids)
  if selected == nil then return nil, nil, rejection(code, message) end
  local number = address.frame_number
  if type(number) ~= "number" or number % 1 ~= 0 or number < 1 or number > #sprite.frames then
    return nil,
      nil,
      rejection("cel_frame_out_of_bounds", "Frame Number is outside the Sprite timeline")
  end
  return selected.layer, selected.path, nil
end

function module.list(sprite, layer, path, from_frame, to_frame)
  if from_frame > to_frame or to_frame > #sprite.frames then
    return rejection("cel_frame_out_of_bounds", "Frame Range is outside the Sprite timeline")
  end
  local cels = {}
  for number = from_frame, to_frame do
    cels[#cels + 1] = module.inspect(sprite, layer, path, number)
  end
  return { cels = cels, selected_path = path }
end

function module.prevalidate(sprite, layer, frame_number, operation, background_color, frame)
  local cel = layer.isImage and layer:cel(frame_number) or nil
  if operation == "add" then
    if not is_regular_transparent(layer) then
      return rejection("cel_unsupported_target", "Cel add requires a regular Transparent Layer")
    end
    if cel ~= nil then return rejection("cel_already_exists", "Cel already exists") end
  elseif operation == "remove" then
    if layer.isBackground or not is_regular_transparent(layer) then
      return rejection("cel_unsupported_target", "Cel remove requires a regular Transparent Layer")
    end
    if cel == nil then return rejection("cel_not_found", "Cel does not exist") end
  elseif operation == "clear" then
    if not is_regular_transparent(layer) and not layer.isBackground then
      return rejection(
        "cel_unsupported_target",
        "Cel clear requires a regular Transparent or Background Layer"
      )
    end
    if cel == nil or cel.image == nil then
      return rejection("cel_not_found", "Cel or Image does not exist")
    end
    if layer.isBackground then
      if background_color == nil then
        return rejection(
          "cel_background_color_required",
          "Background Cel clear requires background_color"
        )
      end
      local valid = pcall(frame.background_color_for_frame, sprite, background_color, frame_number)
      if not valid then
        return rejection(
          "cel_background_color_incompatible",
          "Background Color is incompatible with Sprite Color Mode or Frame Palette"
        )
      end
    elseif background_color ~= nil then
      return rejection(
        "cel_unsupported_target",
        "Transparent Cel clear does not accept background_color"
      )
    end
  else
    error("unsupported Cel operation")
  end
  return nil
end

function module.apply(sprite, layer, frame_number, operation, background_color, frame)
  app.transaction(operation .. " Cel", function()
    if operation == "add" then
      sprite:newCel(layer, frame_number)
    elseif operation == "remove" then
      sprite:deleteCel(layer, frame_number)
    elseif layer.isBackground then
      local _, pixel = frame.background_color_for_frame(sprite, background_color, frame_number)
      layer:cel(frame_number).image:clear(pixel)
    else
      layer:cel(frame_number).image:clear()
    end
  end)
end

function module.add_live(sprite, input, selection, verified_uuids)
  local layer, path, rejected = module.resolve(sprite, input.target, selection, verified_uuids)
  if rejected then return rejected end
  local number = input.target.frame_number
  rejected = module.prevalidate(sprite, layer, number, "add", nil, nil)
  if rejected then return rejected end
  local before = module.inspect(sprite, layer, path, number)
  local before_count = #sprite.cels
  module.apply(sprite, layer, number, "add", nil, nil)
  local after = module.inspect(sprite, layer, path, number)
  assert(after.exists and after.content == "transparent", "added Cel is not transparent")
  assert(#sprite.cels == before_count + 1, "Cel add changed unexpected Cel count")
  return { before = before, before_cel_count = before_count, cel = after }
end

return module
