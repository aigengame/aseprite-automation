-- Packaged Tile lifecycle handler; staged persistence consumes the working Sprite.
local lifecycle = dofile(app.params.tile_lifecycle)
local inspection = dofile(app.params.inspection)
local persistence = dofile(app.params.persistence)
local opened
local previous_compose = app.preferences.experimental.compose_groups
local previous = { sprite = app.activeSprite, layer = app.activeLayer, frame = app.activeFrame }

local function execute()
  local file = assert(io.open(app.params.request, "rb"))
  local request = json.decode(file:read("*a"))
  file:close()
  assert(request.kernel_protocol_version == 1, "unsupported Kernel Protocol version")
  local payload = assert(request.payload)
  app.preferences.experimental.compose_groups = true
  opened = assert(app.open(payload.source_sprite_file), "could not open Source Sprite")
  local uuids = inspection.saved_layer_uuids(opened, payload.source_sprite_file)
  local context, failure = lifecycle.prepare(opened, payload, uuids)
  if failure then return failure end
  lifecycle.apply(opened, payload, context)
  lifecycle.verify_live(opened, payload, context, uuids)
  local live = opened
  opened = nil
  opened, uuids =
    persistence.save_verified(live, payload.staged_sprite_file, uuids, "Tile lifecycle")
  lifecycle.verify_saved(opened, context)
  return lifecycle.observe(opened, payload, context, uuids)
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
