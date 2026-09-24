-- Fixed packaged Cel mutation handler. Runtime files carry data only.
local kernel_protocol_version = 1
local inspection = dofile(app.params.inspection)
local selection = dofile(app.params.layer_select)
local cel = dofile(app.params.cel)
local frame = dofile(app.params.frame)
local persistence = dofile(app.params.persistence)
local digest = dofile(app.params.digest)
local all_sections = { "frames", "tags", "palettes", "layers", "cels", "slices", "tilesets" }
local open_sprite = nil
local previous = {
  sprite = app.activeSprite,
  layer = app.activeLayer,
  frame = app.activeFrame,
  background_color = app.bgColor,
}

local function execute()
  local request_file = assert(io.open(app.params.request, "rb"))
  local request = json.decode(request_file:read("*a"))
  request_file:close()
  assert(request.kernel_protocol_version == kernel_protocol_version, "unsupported Kernel Protocol version")
  local payload = assert(request.payload)
  open_sprite = assert(app.open(payload.source_sprite_file), "could not open Source Sprite File")
  local uuids = inspection.saved_layer_uuids(open_sprite, payload.source_sprite_file)
  local layer, path, rejected = cel.resolve(open_sprite, payload.target, selection, uuids)
  if rejected then return rejected end
  local number = payload.target.frame_number
  rejected = cel.prevalidate(open_sprite, layer, number, payload.operation, payload.background_color, frame)
  if rejected then return rejected end
  local before = cel.inspect(open_sprite, layer, path, number)
  local before_count = #open_sprite.cels
  cel.apply(open_sprite, layer, number, payload.operation, payload.background_color, frame)
  local live = persistence.snapshot(open_sprite, inspection, digest, all_sections, uuids)
  local expected_count = before_count + (payload.operation == "add" and 1 or payload.operation == "remove" and -1 or 0)
  assert(#open_sprite.cels == expected_count, "Cel mutation changed unexpected Cel count")
  local changed = cel.inspect(open_sprite, layer, path, number)
  if payload.operation == "remove" then
    assert(not changed.exists, "removed Cel remains present")
  else
    assert(changed.exists, "added or cleared Cel is absent")
    if payload.operation == "add" or (payload.operation == "clear" and not layer.isBackground) then
      assert(changed.content == "transparent", "Cel Image is not transparent")
    end
    if payload.operation == "clear" and layer.isBackground then
      local _, pixel = frame.background_color_for_frame(open_sprite, payload.background_color, number)
      for value in layer:cel(number).image:pixels() do
        assert(value() == pixel, "Background Cel fill differs from the request")
      end
    end
  end
  assert(open_sprite:saveAs(payload.staged_sprite_file), "could not save staged Sprite")
  open_sprite:close()
  open_sprite = assert(app.open(payload.staged_sprite_file), "could not reopen staged Sprite")
  local reopened_uuids = inspection.saved_layer_uuids(open_sprite, payload.staged_sprite_file)
  local reopened = persistence.snapshot(open_sprite, inspection, digest, all_sections, reopened_uuids)
  persistence.assert_same(live, reopened, "Cel mutation")
  local selected, code, message = selection.resolve(open_sprite, payload.target.layer, reopened_uuids)
  assert(selected ~= nil, code or message or "mutated Layer disappeared")
  local after = cel.inspect(open_sprite, selected.layer, selected.path, number)
  assert(after.exists == changed.exists and after.content == changed.content, "persisted Cel state changed")
  open_sprite:close()
  open_sprite = nil
  return {
    before = before,
    before_cel_count = before_count,
    cel = after,
    sprite = reopened.sprite,
    persisted_reopen_verified = true,
  }
end

local ok, result = pcall(execute)
if open_sprite ~= nil then pcall(function() open_sprite:close() end) end
pcall(function() app.bgColor = previous.background_color end)
if previous.sprite ~= nil and previous.sprite.isValid then
  pcall(function() app.activeSprite = previous.sprite end)
  pcall(function() app.activeLayer = previous.layer end)
  pcall(function() app.activeFrame = previous.frame end)
end
local response
if ok then
  response = { kernel_protocol_version = kernel_protocol_version, status = "ok", result = result }
else
  response = { kernel_protocol_version = kernel_protocol_version, status = "error", cause = "operation_rejected", message = tostring(result) }
end
local response_file = assert(io.open(app.params.response, "wb"))
response_file:write(json.encode(response))
response_file:close()
