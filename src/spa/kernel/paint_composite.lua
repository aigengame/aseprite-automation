-- One all-or-nothing native composition followed by persisted document verification.
local composite = dofile(app.params.paint_composite)
local inspection = dofile(app.params.inspection)
local persistence = dofile(app.params.persistence)
local selection = dofile(app.params.layer_select)
local cels = dofile(app.params.cel)
local digest = dofile(app.params.digest)
local snapshot = dofile(app.params.image_snapshot)
local sections = { "frames", "tags", "palettes", "layers", "cels", "slices", "tilesets" }
local opened = nil
local previous_compose = app.preferences.experimental.compose_groups
local previous = { sprite = app.activeSprite, layer = app.activeLayer, frame = app.activeFrame }

local function reject(code, message) return { rejection = { code = code, message = message } } end

local function execute()
  local file = assert(io.open(app.params.request, "rb"))
  local request = json.decode(file:read("*a"))
  file:close()
  assert(request.kernel_protocol_version == 1, "unsupported Kernel Protocol")
  local payload = assert(request.payload)
  app.preferences.experimental.compose_groups = true
  opened = assert(app.open(payload.source_sprite_file), "could not open Source Sprite")
  local uuids = inspection.saved_layer_uuids(opened, payload.source_sprite_file)
  local layer, path, rejected = cels.resolve(opened, payload.target, selection, uuids)
  if rejected then return rejected end
  if not layer.isImage or layer.isTilemap or layer.isReference then
    return reject("cel_unsupported_target", "Paint composite requires a regular raster Cel")
  end
  local target = layer:cel(payload.target.frame_number)
  if target == nil then return reject("cel_not_found", "Cel does not exist") end
  local image = target.image
  local is_background = layer.isBackground
  local affected = cels.affected(opened, image)
  local before_digest = digest.image_content(image, snapshot.mode(image))
  local expected = persistence.snapshot(opened, inspection, digest, sections, uuids)
  local valid, replacement, facts =
    pcall(composite.compose, image, target, payload, opened, affected)
  if not valid then return reject("paint_composite_invalid", tostring(replacement)) end
  if layer.isBackground and image.colorMode ~= ColorMode.INDEXED then
    for pixel in replacement:pixels() do
      local alpha = image.colorMode == ColorMode.RGB and app.pixelColor.rgbaA(pixel())
        or app.pixelColor.grayaA(pixel())
      if alpha ~= 255 then
        return reject("paint_composite_invalid", "Background output must be opaque")
      end
    end
  end
  for index, cel in ipairs(opened.cels) do
    if cel.image == image then
      expected.images[index].content = digest.fnv1a64(replacement.bytes)
    end
  end
  app.transaction("Composite Snapshot", function()
    for _, run in ipairs(facts.applied_runs) do
      for x = run.x, run.x + run.length - 1 do
        image:putPixel(x, run.y, replacement:getPixel(x, run.y))
      end
    end
  end)
  local live = persistence.snapshot(opened, inspection, digest, sections, uuids)
  persistence.assert_same(expected, live, "Paint composite invariant")
  local after_digest = digest.image_content(image, snapshot.mode(image))
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
  persistence.assert_same(live, reopened, "Paint composite")
  local reopened_layer = assert(selection.resolve(opened, { layer_path = path }, {})).layer
  facts.target = { layer = { layer_path = path }, frame_number = payload.target.frame_number }
  facts.affected_cels = cels.affected(opened, reopened_layer:cel(payload.target.frame_number).image)
  facts.before_content_digest, facts.after_content_digest = before_digest, after_digest
  facts.native_sharing_preserved, facts.geometry_unchanged, facts.persisted_reopen_verified =
    true, true, true
  facts.background_opaque, facts.sprite = is_background, reopened.sprite
  return facts
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
