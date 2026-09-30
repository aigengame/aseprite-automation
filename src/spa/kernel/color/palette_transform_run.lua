-- Fixed Palette organization lifecycle: resolve, mutate, save/reopen, return evidence.
local transforms = dofile(app.params.palette_transform)
local palettes = dofile(app.params.palette)
local inspection = dofile(app.params.inspection)
local persistence = dofile(app.params.persistence)
local sprite = nil
local previous = { sprite = app.activeSprite, layer = app.activeLayer, frame = app.activeFrame }

local function execute()
  local file = assert(io.open(app.params.request, "rb"))
  local request = json.decode(file:read("*a"))
  file:close()
  assert(request.kernel_protocol_version == 1, "unsupported Kernel Protocol version")
  local payload = assert(request.payload)
  sprite = assert(app.open(payload.source_sprite_file), "could not open Source Sprite File")
  local uuids = inspection.saved_layer_uuids(sprite, payload.source_sprite_file)
  local execute_operation = assert(
    ({ resize = transforms.resize, remap = transforms.remap, reorder = transforms.reorder })[payload.operation]
  )
  local live = execute_operation(sprite, payload, uuids)
  if live.rejection then return live end
  local live_facts = transforms.snapshot(sprite, uuids)
  sprite, uuids = persistence.save_verified(
    sprite,
    payload.staged_sprite_file,
    uuids,
    "Palette " .. payload.operation
  )
  persistence.assert_equal(
    live_facts,
    transforms.snapshot(sprite, uuids),
    "Persisted Palette Images and metadata"
  )
  local persisted = palettes.list(sprite)
  persistence.assert_equal(
    { frame_count = live.frame_count, palette_changes = live.palette_changes },
    persisted,
    "Persisted Palette timeline"
  )
  if payload.operation == "resize" then
    live.palette = palettes.get(sprite, payload.palette_frame_number).palette
  end
  live.persisted_reopen_verified = true
  return live
end

local ok, result = pcall(execute)
if sprite ~= nil then pcall(function() sprite:close() end) end
if previous.sprite ~= nil and previous.sprite.isValid then
  pcall(function() app.activeSprite = previous.sprite end)
  pcall(function() app.activeLayer = previous.layer end)
  pcall(function() app.activeFrame = previous.frame end)
end
local response
if ok then
  response = { kernel_protocol_version = 1, status = "ok", result = result }
else
  response = {
    kernel_protocol_version = 1,
    status = "error",
    cause = "operation_rejected",
    message = tostring(result),
  }
end
local file = assert(io.open(app.params.response, "wb"))
file:write(json.encode(response))
file:close()
