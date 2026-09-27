-- Fixed Image observation handler; Source is never saved.
local inspection = dofile(app.params.inspection)
local selection = dofile(app.params.layer_select)
local cel = dofile(app.params.cel)
local snapshot = dofile(app.params.image_snapshot)
local colors = dofile(app.params.raster_color)
local composition = dofile(app.params.layer_composition)
local opened = nil
local previous = { sprite = app.activeSprite, layer = app.activeLayer, frame = app.activeFrame }

local function reject(code, message) return { rejection = { code = code, message = message } } end
local function within(area, width, height)
  return area.width > 0
    and area.height > 0
    and area.x >= 0
    and area.y >= 0
    and area.x + area.width <= width
    and area.y + area.height <= height
end

local function individual(source, uuids)
  local layer, path, rejected = cel.resolve(opened, source.target, selection, uuids)
  if rejected then return nil, nil, nil, rejected end
  if not layer.isImage or layer.isTilemap then
    return nil, nil, nil, reject("cel_unsupported_target", "Image Get requires a raster Cel")
  end
  local target = layer:cel(source.target.frame_number)
  if target == nil then return nil, nil, nil, reject("cel_not_found", "Cel does not exist") end
  local image = target.image
  if not within(source.rectangle, image.width, image.height) then
    return nil,
      nil,
      nil,
      reject("image_rectangle_out_of_bounds", "Rectangle exceeds Cel Image bounds")
  end
  return image,
    source.rectangle,
    {
      kind = "individual",
      coordinate_space = "image-pixel",
      rectangle = snapshot.rectangle(source.rectangle),
      target = { layer = { layer_path = path }, frame_number = source.target.frame_number },
      layer_kind = layer.isReference and "reference"
        or layer.isBackground and "background"
        or "transparent",
      image_size = { width = image.width, height = image.height },
      associated_cels = cel.affected(opened, image),
    },
    nil
end

local function composite(source, uuids)
  if source.frame_number > #opened.frames then
    return nil, nil, nil, reject("cel_frame_out_of_bounds", "Frame Number exceeds timeline")
  end
  if not within(source.rectangle, opened.width, opened.height) then
    return nil,
      nil,
      nil,
      reject("image_rectangle_out_of_bounds", "Rectangle exceeds Sprite Canvas bounds")
  end
  local image, paths, rejected = composition.render(
    opened,
    source.frame_number,
    source.layer_composition,
    source.rectangle,
    selection,
    uuids,
    source.output_color_mode
  )
  if rejected then return nil, nil, nil, rejected end
  return image,
    { x = 0, y = 0, width = image.width, height = image.height },
    {
      kind = "composite",
      output_color_mode = source.output_color_mode,
      color_mode = snapshot.mode(opened),
      mask_color = snapshot.color(opened.spec.transparentColor, snapshot.mode(opened)),
      coordinate_space = "canvas-pixel",
      rectangle = snapshot.rectangle(source.rectangle),
      frame_number = source.frame_number,
      layer_composition = composition.copy(source.layer_composition),
      resolved_layer_paths = paths,
      compose_groups = true,
      reference_layers_rendered = false,
    },
    nil
end

local function execute()
  local file = assert(io.open(app.params.request, "rb"))
  local request = json.decode(file:read("*a"))
  file:close()
  assert(request.kernel_protocol_version == 1, "unsupported Kernel Protocol")
  local payload = request.payload
  opened = assert(app.open(payload.sprite_file), "could not open Sprite File")
  local source = payload.source
  local uuids = inspection.saved_layer_uuids(opened, payload.sprite_file)
  local image, area, facts, rejected
  if source.kind == "individual" then
    image, area, facts, rejected = individual(source, uuids)
  else
    assert(source.kind == "composite", "unsupported Image source kind")
    image, area, facts, rejected = composite(source, uuids)
  end
  if rejected then return rejected end
  local value, used = snapshot.read(image, area), {}
  if image.colorMode == ColorMode.INDEXED then
    for _, row in ipairs(value.rows) do
      for _, run in ipairs(row) do
        used[run.color.index] = true
      end
    end
  end
  local inline = value
  if payload.staged_snapshot_file ~= nil then
    local output = assert(io.open(payload.staged_snapshot_file, "wb"))
    assert(output:write(json.encode(value)))
    assert(output:close())
    inline = json.decode("null")
  else
    assert(area.width * area.height <= 4096, "inline Snapshot exceeds 4096 pixels")
  end
  local frame_number = source.kind == "individual" and source.target.frame_number
    or source.frame_number
  return {
    width = area.width,
    height = area.height,
    color_mode = snapshot.mode(image),
    source = facts,
    snapshot = inline,
    mask_color = snapshot.color(image.spec.transparentColor, snapshot.mode(image)),
    effective_palettes = colors.palette_facts(opened, { { frame_number = frame_number } }, used),
  }
end

local ok, result = pcall(execute)
if opened ~= nil then pcall(function() opened:close() end) end
if previous.sprite ~= nil and previous.sprite.isValid then
  app.activeSprite, app.activeLayer, app.activeFrame =
    previous.sprite, previous.layer, previous.frame
end
local response = ok and { kernel_protocol_version = 1, status = "ok", result = result }
  or {
    kernel_protocol_version = 1,
    status = "error",
    cause = "operation_rejected",
    message = tostring(result),
  }
local file = assert(io.open(app.params.response, "wb"))
file:write(json.encode(response))
file:close()
