-- Fixed Image observation handler; Source is never saved.
local inspection = dofile(app.params.inspection)
local selection = dofile(app.params.layer_select)
local cel = dofile(app.params.cel)
local snapshot = dofile(app.params.image_snapshot)
local colors = dofile(app.params.raster_color)
local opened = nil

local function execute()
  local file = assert(io.open(app.params.request, "rb"))
  local request = json.decode(file:read("*a"))
  file:close()
  assert(request.kernel_protocol_version == 1, "unsupported Kernel Protocol")
  local payload = request.payload
  opened = assert(app.open(payload.sprite_file), "could not open Sprite File")
  local source = payload.source
  local uuids = inspection.saved_layer_uuids(opened, payload.sprite_file)
  local layer, path, rejected = cel.resolve(opened, source.target, selection, uuids)
  if rejected then return rejected end
  if not layer.isImage or layer.isTilemap then
    return {
      rejection = { code = "cel_unsupported_target", message = "Image Get requires a raster Cel" },
    }
  end
  local target = layer:cel(source.target.frame_number)
  if target == nil then
    return { rejection = { code = "cel_not_found", message = "Cel does not exist" } }
  end
  local image = target.image
  local value = snapshot.read(image, source.rectangle)
  local used = {}
  if image.colorMode == ColorMode.INDEXED then
    for _, row in ipairs(value.rows) do
      for _, run in ipairs(row) do
        used[run.color.index] = true
      end
    end
  end
  return {
    source = {
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
    snapshot = value,
    mask_color = snapshot.color(image.spec.transparentColor, snapshot.mode(image)),
    effective_palettes = colors.palette_facts(
      opened,
      { { frame_number = source.target.frame_number } },
      used
    ),
  }
end

local ok, result = pcall(execute)
if opened ~= nil then pcall(function() opened:close() end) end
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
