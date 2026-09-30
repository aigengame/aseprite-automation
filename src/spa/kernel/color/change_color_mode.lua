-- Standalone publication uses the same attached-Sprite conversion as Plan.
local color_mode = dofile(app.params.color_mode)
local inspection = dofile(app.params.inspection)
local persistence = dofile(app.params.persistence)
local sprite = nil
local previous = { sprite = app.activeSprite, layer = app.activeLayer, frame = app.activeFrame }
local function execute()
  local file = assert(io.open(app.params.request, "rb"))
  local request = json.decode(file:read("*a"))
  file:close()
  assert(request.kernel_protocol_version == 1, "unsupported Kernel Protocol version")
  local payload = request.payload
  sprite = assert(app.open(payload.source_sprite_file), "could not open Source Sprite File")
  local uuids = inspection.saved_layer_uuids(sprite, payload.source_sprite_file)
  local result = color_mode.change(sprite, payload.conversion)
  sprite = persistence.save_verified(sprite, payload.staged_sprite_file, uuids, "Change Color Mode")
  local persisted = color_mode.observe(sprite)
  persistence.assert_equal(result.after, persisted, "Persisted Change Color Mode")
  result.after = persisted
  result.persisted_reopen_verified = true
  return result
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
