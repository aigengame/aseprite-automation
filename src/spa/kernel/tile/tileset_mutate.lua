-- Packaged Tileset lifecycle handler; Source publication belongs to orchestration.
local lifecycle = dofile(app.params.tileset_lifecycle)
local inspection = dofile(app.params.inspection)
local persistence = dofile(app.params.persistence)
local opened
local previous_compose = app.preferences.experimental.compose_groups
local previous = { sprite = app.activeSprite, layer = app.activeLayer, frame = app.activeFrame }
local sections = { "frames", "tags", "palettes", "layers", "cels", "slices", "tilesets" }

local function execute()
  local file = assert(io.open(app.params.request, "rb"))
  local request = json.decode(file:read("*a"))
  file:close()
  assert(request.kernel_protocol_version == 1, "unsupported Kernel Protocol version")
  local payload = assert(request.payload)
  app.preferences.experimental.compose_groups = true
  opened = assert(app.open(payload.source_sprite_file), "could not open Source Sprite")
  local uuids = inspection.saved_layer_uuids(opened, payload.source_sprite_file)
  local operation = payload.operation == "remove" and lifecycle.remove_live
    or payload.operation == "rebind" and lifecycle.rebind_live
  assert(operation ~= nil, "unsupported Tileset lifecycle operation")
  local result = operation(opened, payload, uuids)
  if result.rejection then return result end
  local checkpoint = lifecycle.checkpoint(opened, uuids)
  local live = opened
  opened = nil
  opened, uuids =
    persistence.save_verified(live, payload.staged_sprite_file, uuids, "Tileset lifecycle")
  lifecycle.verify_saved(opened, checkpoint, uuids)
  result.sprite = inspection.inspect(opened, sections, uuids)
  result.persisted_reopen_verified = true
  return result
end

local ok, result = pcall(execute)
if opened ~= nil then pcall(function() opened:close() end) end
app.preferences.experimental.compose_groups = previous_compose
if previous.sprite ~= nil and previous.sprite.isValid then
  pcall(function() app.activeSprite = previous.sprite end)
  pcall(function() app.activeLayer = previous.layer end)
  pcall(function() app.activeFrame = previous.frame end)
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
