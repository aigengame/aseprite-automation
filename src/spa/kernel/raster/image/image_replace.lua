-- Complete pixel replacement without assigning Images or Cel geometry.
local inspection = dofile(app.params.inspection)
local persistence = dofile(app.params.persistence)
local selection = dofile(app.params.layer_select)
local cel = dofile(app.params.cel)
local snapshot = dofile(app.params.image_snapshot)
local colors = dofile(app.params.raster_color)
local digest = dofile(app.params.digest)
local sections = { "frames", "tags", "palettes", "layers", "cels", "slices", "tilesets" }
local opened = nil
local previous_compose = app.preferences.experimental.compose_groups
local previous = { sprite = app.activeSprite, layer = app.activeLayer, frame = app.activeFrame }

local function reject(code, message) return { rejection = { code = code, message = message } } end

local function replacement_image(image, value, background)
  assert(value.coordinate_space == "image-pixel", "Snapshot must use Image Pixels")
  assert(value.color_mode == snapshot.mode(image), "Snapshot Color Mode differs")
  local area = assert(value.rectangle)
  assert(
    area.x == 0 and area.y == 0 and area.width == image.width and area.height == image.height,
    "Snapshot must cover the complete Image bounds"
  )
  return snapshot.materialize(value, image.spec, background)
end

local function execute()
  local file = assert(io.open(app.params.request, "rb"))
  local request = json.decode(file:read("*a"))
  file:close()
  assert(request.kernel_protocol_version == 1, "unsupported Kernel Protocol")
  local payload = request.payload
  -- Group facts must remain observable during persistence verification. In batch,
  -- some runtimes omit them on save; detecting that loss prevents Target Commit.
  app.preferences.experimental.compose_groups = true
  opened = assert(app.open(payload.source_sprite_file), "could not open Source Sprite")
  local uuids = inspection.saved_layer_uuids(opened, payload.source_sprite_file)
  local layer, path, rejected = cel.resolve(opened, payload.target, selection, uuids)
  if rejected then return rejected end
  if not layer.isImage or layer.isTilemap then
    return reject("cel_unsupported_target", "Image Replace requires a raster Cel")
  end
  local target = layer:cel(payload.target.frame_number)
  if target == nil then return reject("cel_not_found", "Cel does not exist") end
  local image = target.image
  local affected = cel.affected(opened, image)
  local valid, replacement, used =
    pcall(replacement_image, image, payload.input.snapshot, layer.isBackground)
  if not valid then return reject("image_snapshot_invalid", tostring(replacement)) end
  local palettes_ok, palettes = pcall(colors.palette_facts, opened, affected, used)
  if not palettes_ok then return reject("image_snapshot_invalid", tostring(palettes)) end
  for _, state in ipairs(affected) do
    if state.is_background then
      for _, fact in ipairs(palettes) do
        if fact.frame_number == state.frame_number then
          for _, index in ipairs(fact.indexes) do
            if index.color.alpha ~= 255 then
              return reject("image_snapshot_invalid", "Background Palette colors must be opaque")
            end
          end
        end
      end
    end
  end
  local mode = snapshot.mode(image)
  local before_digest = digest.image_content(image, mode)
  local expected = persistence.snapshot(opened, inspection, digest, sections, uuids)
  for index, current in ipairs(opened.cels) do
    if current.image == image then
      expected.images[index].content = digest.fnv1a64(replacement.bytes)
    end
  end
  app.transaction("Replace Image pixels", function()
    for y = 0, image.height - 1 do
      for x = 0, image.width - 1 do
        image:putPixel(x, y, replacement:getPixel(x, y))
      end
    end
  end)
  local live = persistence.snapshot(opened, inspection, digest, sections, uuids)
  persistence.assert_same(expected, live, "Image Replace invariant")
  local after_digest = digest.image_content(image, mode)
  local width, height = image.width, image.height
  assert(opened:saveAs(payload.staged_sprite_file), "could not save staged Sprite")
  opened:close()
  opened = assert(app.open(payload.staged_sprite_file), "could not reopen staged Sprite")
  local reopened = persistence.snapshot(
    opened,
    inspection,
    digest,
    sections,
    inspection.saved_layer_uuids(opened, payload.staged_sprite_file)
  )
  persistence.assert_same(live, reopened, "Image Replace")
  local reopened_layer = assert(selection.resolve(opened, { layer_path = path }, {})).layer
  local reopened_target = assert(reopened_layer:cel(payload.target.frame_number))
  return {
    input_form = payload.input.kind,
    target = { layer = { layer_path = path }, frame_number = payload.target.frame_number },
    color_mode = mode,
    width = width,
    height = height,
    affected_cels = cel.affected(opened, reopened_target.image),
    effective_palettes = palettes,
    before_content_digest = before_digest,
    after_content_digest = after_digest,
    geometry_unchanged = true,
    native_sharing_preserved = true,
    persisted_reopen_verified = true,
    sprite = reopened.sprite,
  }
end

local ok, result = pcall(execute)
if opened ~= nil then pcall(function() opened:close() end) end
app.preferences.experimental.compose_groups = previous_compose
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
