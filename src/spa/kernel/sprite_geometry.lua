-- Fixed packaged Sprite resize/crop semantics. Runtime files carry data only.
local kernel_protocol_version = 1
local inspection = dofile(app.params.inspection)
local persistence = dofile(app.params.persistence)
local digest = dofile(app.params.digest)
local all_sections = { "frames", "tags", "palettes", "layers", "cels", "slices", "tilesets" }
local open_sprite = nil

local function tilemap_layer_count(layers)
  local count = 0
  for _, layer in ipairs(layers) do
    if layer.isTilemap then count = count + 1 end
    if layer.isGroup then count = count + tilemap_layer_count(layer.layers) end
  end
  return count
end

local function tilemap_content(sprite)
  local cels, images = 0, 0
  for _, cel in ipairs(sprite.cels) do
    if cel.layer.isTilemap then cels = cels + 1 end
    if cel.image ~= nil and cel.image.colorMode == ColorMode.TILEMAP then
      images = images + 1
    end
  end
  return {
    kind = "sprite_content",
    tileset_count = #sprite.tilesets,
    tilemap_layer_count = tilemap_layer_count(sprite.layers),
    tilemap_cel_count = cels,
    tilemap_image_count = images,
  }
end

local function execute()
  local request_file = assert(io.open(app.params.request, "rb"))
  local request = json.decode(request_file:read("*a"))
  request_file:close()
  assert(request.kernel_protocol_version == kernel_protocol_version, "unsupported Kernel Protocol version")
  local payload = assert(request.payload)
  assert(payload.operation == "resize" or payload.operation == "crop", "unsupported Sprite geometry operation")
  open_sprite = assert(app.open(payload.source_sprite_file), "could not open Source Sprite File")
  local content = tilemap_content(open_sprite)
  if
    content.tileset_count > 0
    or content.tilemap_layer_count > 0
    or content.tilemap_cel_count > 0
    or content.tilemap_image_count > 0
  then
    open_sprite:close()
    open_sprite = nil
    return { rejection = content }
  end

  local rectangle = payload.rectangle
  if payload.operation == "crop" then
    assert(rectangle ~= nil, "missing Crop Rectangle")
    if
      rectangle.x < 0
      or rectangle.y < 0
      or rectangle.width < 1
      or rectangle.height < 1
      or rectangle.x + rectangle.width > open_sprite.width
      or rectangle.y + rectangle.height > open_sprite.height
    then
      local canvas = { width = open_sprite.width, height = open_sprite.height }
      local rejected_rectangle = {
        x = rectangle.x,
        y = rectangle.y,
        width = rectangle.width,
        height = rectangle.height,
      }
      open_sprite:close()
      open_sprite = nil
      return { rejection = { kind = "crop_bounds", rectangle = rejected_rectangle, canvas = canvas } }
    end
  end

  local verified_uuids = inspection.saved_layer_uuids(open_sprite, payload.source_sprite_file)
  local before = inspection.inspect(open_sprite, all_sections, verified_uuids)
  if payload.operation == "resize" then
    -- Sprite:resize delegates to SpriteSize with UI disabled; its fixed default is nearest neighbor.
    open_sprite:resize(Size(payload.width, payload.height))
  else
    -- Unlike Sprite:crop, CanvasSize with trimOutside removes outside Cel pixels.
    app.activeSprite = open_sprite
    app.command.CanvasSize {
      bounds = Rectangle(rectangle.x, rectangle.y, rectangle.width, rectangle.height),
      trimOutside = true,
      ui = false,
    }
  end
  local after_live = persistence.snapshot(open_sprite, inspection, digest, all_sections, {})
  assert(open_sprite:saveAs(payload.staged_sprite_file), "could not save staged Sprite")
  open_sprite:close()
  open_sprite = assert(app.open(payload.staged_sprite_file), "could not reopen staged Sprite")
  verified_uuids = inspection.saved_layer_uuids(open_sprite, payload.staged_sprite_file)
  local after = persistence.snapshot(open_sprite, inspection, digest, all_sections, verified_uuids)
  persistence.assert_same(after_live, after, "Sprite " .. payload.operation)
  open_sprite:close()
  open_sprite = nil
  return {
    before_sprite = before,
    sprite = after.sprite,
    persisted_reopen_verified = true,
  }
end

local ok, result = pcall(execute)
if open_sprite ~= nil then pcall(function() open_sprite:close() end) end
local response
if ok then
  response = { kernel_protocol_version = kernel_protocol_version, status = "ok", result = result }
else
  response = {
    kernel_protocol_version = kernel_protocol_version,
    status = "error",
    cause = "operation_rejected",
    message = tostring(result),
  }
end
local response_file = assert(io.open(app.params.response, "wb"))
response_file:write(json.encode(response))
response_file:close()
