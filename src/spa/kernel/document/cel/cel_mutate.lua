-- Fixed packaged Cel mutation handler. Runtime files carry data only.
local kernel_protocol_version = 1
local inspection = dofile(app.params.inspection)
local selection = dofile(app.params.layer_select)
local cel = dofile(app.params.cel)
local tile_creation = dofile(app.params.tile_cel_add)
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

local function same_path(left, right)
  if #left ~= #right then return false end
  for index = 1, #left do
    if left[index] ~= right[index] then return false end
  end
  return true
end

local function assert_affected(before, after, background)
  assert(#before == #after, "Cel clear changed linked Cel scope")
  for index, prior in ipairs(before) do
    local current = after[index]
    assert(
      same_path(prior.layer_path, current.layer_path)
        and prior.frame_number == current.frame_number
        and current.exists
        and current.is_background == prior.is_background
        and current.content == (background and "nonempty" or "transparent"),
      "Cel clear changed or failed an affected Cel"
    )
    assert(#prior.linked_cels == #current.linked_cels, "Cel clear changed native links")
    for link_index, link in ipairs(prior.linked_cels) do
      local actual = current.linked_cels[link_index]
      assert(
        same_path(link.layer_path, actual.layer_path) and link.frame_number == actual.frame_number,
        "Cel clear changed native links"
      )
    end
  end
end

local function execute()
  local request_file = assert(io.open(app.params.request, "rb"))
  local request = json.decode(request_file:read("*a"))
  request_file:close()
  assert(
    request.kernel_protocol_version == kernel_protocol_version,
    "unsupported Kernel Protocol version"
  )
  local payload = assert(request.payload)
  open_sprite = assert(app.open(payload.source_sprite_file), "could not open Source Sprite File")
  local uuids = inspection.saved_layer_uuids(open_sprite, payload.source_sprite_file)
  local layer, path, rejected = cel.resolve(open_sprite, payload.target, selection, uuids)
  if rejected then return rejected end
  local number = payload.target.frame_number
  local target_background = layer.isBackground
  if payload.operation ~= "add" then
    rejected = cel.prevalidate(
      open_sprite,
      layer,
      number,
      payload.operation,
      payload.background_color,
      frame
    )
    if rejected then return rejected end
  end
  local affected_before = nil
  if payload.operation == "clear" then
    local image = layer:cel(number).image
    affected_before = cel.affected(open_sprite, image)
    for _, current in ipairs(open_sprite.cels) do
      if current.image == image and current.layer ~= layer then
        local peer = current.layer
        if
          peer.isBackground ~= target_background
          or (not target_background and not cel.is_regular_transparent(peer))
        then
          return {
            rejection = {
              code = "cel_unsupported_target",
              message = "Linked Cel clear includes an unsupported Layer",
            },
          }
        end
      end
    end
  end
  local before = cel.inspect(open_sprite, layer, path, number)
  local before_count = #open_sprite.cels
  if payload.operation == "add" then
    local added = cel.add_live(open_sprite, payload, selection, uuids, tile_creation.add)
    if added.rejection then return added end
  else
    cel.apply(
      open_sprite,
      layer,
      number,
      payload.operation,
      payload.background_color,
      frame,
      payload.image_size
    )
  end
  local live = persistence.snapshot(open_sprite, inspection, digest, all_sections, uuids)
  local expected_count = before_count
    + (payload.operation == "add" and 1 or payload.operation == "remove" and -1 or 0)
  assert(#open_sprite.cels == expected_count, "Cel mutation changed unexpected Cel count")
  local changed = cel.inspect(open_sprite, layer, path, number)
  local affected_live = nil
  if affected_before ~= nil then
    affected_live = cel.affected(open_sprite, layer:cel(number).image)
    assert_affected(affected_before, affected_live, target_background)
  end
  if payload.operation == "remove" then
    assert(not changed.exists, "removed Cel remains present")
  else
    assert(changed.exists, "added or cleared Cel is absent")
    if payload.operation == "add" or (payload.operation == "clear" and not layer.isBackground) then
      assert(changed.content == "transparent", "Cel Image is not transparent")
    end
    if payload.operation == "clear" and layer.isBackground then
      local _, pixel =
        frame.background_color_for_frame(open_sprite, payload.background_color, number)
      for value in layer:cel(number).image:pixels() do
        assert(value() == pixel, "Background Cel fill differs from the request")
      end
    end
  end
  assert(open_sprite:saveAs(payload.staged_sprite_file), "could not save staged Sprite")
  open_sprite:close()
  open_sprite = assert(app.open(payload.staged_sprite_file), "could not reopen staged Sprite")
  local reopened_uuids = inspection.saved_layer_uuids(open_sprite, payload.staged_sprite_file)
  local reopened =
    persistence.snapshot(open_sprite, inspection, digest, all_sections, reopened_uuids)
  persistence.assert_same(live, reopened, "Cel mutation")
  local selected, code, message =
    selection.resolve(open_sprite, payload.target.layer, reopened_uuids)
  assert(selected ~= nil, code or message or "mutated Layer disappeared")
  local after = cel.inspect(open_sprite, selected.layer, selected.path, number)
  assert(
    after.exists == changed.exists and after.content == changed.content,
    "persisted Cel state changed"
  )
  local affected_reopened = nil
  if affected_live ~= nil then
    affected_reopened = cel.affected(open_sprite, selected.layer:cel(number).image)
    assert_affected(affected_live, affected_reopened, target_background)
  end
  local tilemap_creation
  if payload.operation == "add" and after.is_tilemap then
    tilemap_creation = tile_creation.observe(open_sprite, selected.layer, number, reopened_uuids)
  end
  open_sprite:close()
  open_sprite = nil
  return {
    before = before,
    before_cel_count = before_count,
    cel = after,
    tilemap_creation = tilemap_creation,
    affected_cels = affected_reopened,
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
