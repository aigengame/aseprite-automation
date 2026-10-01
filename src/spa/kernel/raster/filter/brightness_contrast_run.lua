local filter = dofile(app.params.brightness_contrast)
local inspection = dofile(app.params.inspection)
local persistence = dofile(app.params.persistence)
local support = dofile(app.params.filter_support)
local sprite = nil
local function execute()
  local file = assert(io.open(app.params.request, "rb"))
  local request = json.decode(file:read("*a"))
  file:close()
  assert(request.kernel_protocol_version == 1, "unsupported Kernel Protocol version")
  local payload = request.payload
  sprite = assert(app.open(payload.source_sprite_file), "could not open Source Sprite File")
  local uuids = inspection.saved_layer_uuids(sprite, payload.source_sprite_file)
  local result = filter.apply(sprite, payload, uuids)
  if result.rejection then return result end
  local live = support.snapshot(sprite, uuids)
  sprite, uuids =
    persistence.save_verified(sprite, payload.staged_sprite_file, uuids, "Brightness/Contrast")
  persistence.assert_equal(
    live,
    support.snapshot(sprite, uuids),
    "Persisted Filter Images and Palettes"
  )
  result.persisted_reopen_verified = true
  return result
end
local ok, result = pcall(execute)
if sprite then pcall(function() sprite:close() end) end
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
