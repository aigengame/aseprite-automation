-- Fixed packaged Cel relationship handler. Runtime files carry data only.
local kernel_protocol_version = 1
local inspection = dofile(app.params.inspection)
local selection = dofile(app.params.layer_select)
local cel = dofile(app.params.cel)
local persistence = dofile(app.params.persistence)
local digest = dofile(app.params.digest)
local relationship = dofile(app.params.cel_relationship)
local all_sections = { "frames", "tags", "palettes", "layers", "cels", "slices", "tilesets" }
local open_sprite = nil
local previous = { sprite = app.activeSprite, layer = app.activeLayer, frame = app.activeFrame }

local function execute()
  local request_file = assert(io.open(app.params.request, "rb"))
  local request = json.decode(request_file:read("*a"))
  request_file:close()
  assert(
    request.kernel_protocol_version == kernel_protocol_version,
    "unsupported Kernel Protocol version"
  )
  local payload = assert(request.payload)
  local operation = payload.operation
  open_sprite = assert(app.open(payload.source_sprite_file), "could not open Source Sprite File")
  local uuids = inspection.saved_layer_uuids(open_sprite, payload.source_sprite_file)
  local result = relationship.apply_live(open_sprite, operation, payload, uuids)
  if result.rejection then return result end
  local after, affected = result.cel, result.affected_cels
  local selected_number = after.frame_number
  local live = persistence.snapshot(open_sprite, inspection, digest, all_sections, uuids)
  assert(open_sprite:saveAs(payload.staged_sprite_file), "could not save staged Sprite")
  open_sprite:close()
  open_sprite = assert(app.open(payload.staged_sprite_file), "could not reopen staged Sprite")
  local reopened_uuids = inspection.saved_layer_uuids(open_sprite, payload.staged_sprite_file)
  local reopened =
    persistence.snapshot(open_sprite, inspection, digest, all_sections, reopened_uuids)
  persistence.assert_same(live, reopened, "Cel " .. operation)
  local reopened_selected, code, message =
    selection.resolve(open_sprite, (payload.destination or payload.target).layer, reopened_uuids)
  assert(reopened_selected ~= nil, code or message or "Cel Layer disappeared")
  local reopened_cel =
    cel.inspect(open_sprite, reopened_selected.layer, reopened_selected.path, selected_number)
  assert(reopened_cel.exists and reopened_cel.content == after.content, "persisted Cel changed")
  local reopened_affected = {}
  for _, state in ipairs(affected) do
    local reopened_layer =
      assert(selection.resolve(open_sprite, { layer_path = state.layer_path }, {})).layer
    reopened_affected[#reopened_affected + 1] =
      cel.inspect(open_sprite, reopened_layer, state.layer_path, state.frame_number)
  end
  open_sprite:close()
  open_sprite = nil
  return {
    before_cel_count = result.before_cel_count,
    before_cels = result.before_cels,
    affected_cels = reopened_affected,
    cel = reopened_cel,
    sprite = reopened.sprite,
    persisted_reopen_verified = true,
  }
end

local ok, result = pcall(execute)
if open_sprite ~= nil then pcall(function() open_sprite:close() end) end
if previous.sprite ~= nil and previous.sprite.isValid then
  pcall(function() app.activeSprite = previous.sprite end)
  pcall(function() app.activeLayer = previous.layer end)
  pcall(function() app.activeFrame = previous.frame end)
end
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
