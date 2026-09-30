-- Fixed standalone wrapper; the shared motion owner applies one preflighted change.
local kernel_protocol_version = 1
local motion = dofile(app.params.motion)
local inspection = dofile(app.params.inspection)
local persistence = dofile(app.params.persistence)
local cel = dofile(app.params.cel)
local selection = dofile(app.params.layer_select)
local sprite
local previous = { sprite = app.activeSprite, layer = app.activeLayer, frame = app.activeFrame }

local function execute()
  local file = assert(io.open(app.params.request, "rb"))
  local request = json.decode(file:read("*a"))
  file:close()
  assert(request.kernel_protocol_version == kernel_protocol_version)
  local input = request.payload
  sprite = assert(app.open(input.source_sprite_file))
  local uuids = inspection.saved_layer_uuids(sprite, input.source_sprite_file)
  local result = motion.apply_live(sprite, input, uuids)
  if result.rejection then return result end
  local persisted
  sprite, uuids, persisted =
    persistence.save_verified(sprite, input.staged_sprite_file, uuids, "Motion")
  local selected = assert(selection.resolve(sprite, input.layer, uuids))
  for _, change in ipairs(result.cels) do
    change.after = cel.inspect(sprite, selected.layer, selected.path, change.before.frame_number)
  end
  result.sprite = persisted
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
local response = ok
    and { kernel_protocol_version = kernel_protocol_version, status = "ok", result = result }
  or {
    kernel_protocol_version = kernel_protocol_version,
    status = "error",
    cause = "operation_rejected",
    message = tostring(result),
  }
local file = assert(io.open(app.params.response, "wb"))
file:write(json.encode(response))
file:close()
