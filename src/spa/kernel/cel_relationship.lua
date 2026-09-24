-- Fixed packaged Cel relationship handler. Runtime files carry data only.
local kernel_protocol_version = 1
local inspection = dofile(app.params.inspection)
local selection = dofile(app.params.layer_select)
local cel = dofile(app.params.cel)
local persistence = dofile(app.params.persistence)
local digest = dofile(app.params.digest)
local all_sections = { "frames", "tags", "palettes", "layers", "cels", "slices", "tilesets" }
local open_sprite = nil
local previous = { sprite = app.activeSprite, layer = app.activeLayer, frame = app.activeFrame }

local function reject(code, message, role)
  return { rejection = { code = code, message = message, role = role } }
end

local function regular(layer)
  return layer.isImage
    and layer.isTransparent
    and not layer.isGroup
    and not layer.isReference
    and not layer.isTilemap
    and not layer.isBackground
end

local function resolve(sprite, address, uuids, role)
  local layer, path, refused = cel.resolve(sprite, address, selection, uuids)
  if refused then
    refused.rejection.role = role
    return nil, nil, refused
  end
  if not regular(layer) then
    return nil,
      nil,
      reject("cel_unsupported_target", "Operation requires a regular Transparent Layer", role)
  end
  return layer, path, nil
end

local function key(state)
  local parts = {}
  for _, index in ipairs(state.layer_path) do
    parts[#parts + 1] = tostring(index)
  end
  return table.concat(parts, "/") .. ":" .. state.frame_number
end

local function sort_states(states)
  table.sort(states, function(left, right)
    if left.frame_number ~= right.frame_number then
      return left.frame_number < right.frame_number
    end
    for index = 1, math.min(#left.layer_path, #right.layer_path) do
      if left.layer_path[index] ~= right.layer_path[index] then
        return left.layer_path[index] < right.layer_path[index]
      end
    end
    return #left.layer_path < #right.layer_path
  end)
end

local function affected_before(sprite, layer, path, number)
  local target = layer:cel(number)
  if target == nil then return { cel.inspect(sprite, layer, path, number) } end
  local group = cel.affected(sprite, target.image)
  for _, state in ipairs(group) do
    local selected = selection.resolve(sprite, { layer_path = state.layer_path }, {})
    assert(selected ~= nil, "linked Cel Layer disappeared")
    if not regular(selected.layer) then
      return nil, reject("cel_unsupported_target", "Linked Cel includes an unsupported Layer")
    end
  end
  return group
end

local function apply_link(sprite, layer, source_number, destination_number)
  local temporary = source_number + 1
  sprite:newEmptyFrame(temporary)
  app.range:clear()
  app.activeSprite = sprite
  app.activeLayer = layer
  app.activeFrame = sprite.frames[source_number]
  app.command.NewFrame { content = "cellinked" }
  local generated = assert(layer:cel(temporary), "Aseprite did not create a linked Cel")
  assert(generated.image == layer:cel(source_number).image, "Aseprite copied instead of linked")
  generated.frameNumber = destination_number > source_number and destination_number + 1
    or destination_number
  sprite:deleteFrame(temporary)
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
  local operation = payload.operation
  assert(operation == "set" or operation == "copy" or operation == "link" or operation == "unlink")
  open_sprite = assert(app.open(payload.source_sprite_file), "could not open Source Sprite File")
  local uuids = inspection.saved_layer_uuids(open_sprite, payload.source_sprite_file)
  local primary = payload.source or payload.target
  local role = payload.source and "source" or "target"
  local layer, path, refused = resolve(open_sprite, primary, uuids, role)
  if refused then return refused end
  local number = primary.frame_number
  local source_cel = layer:cel(number)
  if source_cel == nil then return reject("cel_not_found", "Cel does not exist", role) end
  local dest_layer, dest_path, destination_number
  if payload.destination then
    dest_layer, dest_path, refused = resolve(open_sprite, payload.destination, uuids, "destination")
    if refused then return refused end
    destination_number = payload.destination.frame_number
    if operation == "link" and dest_layer ~= layer then
      return reject("cel_unsupported_target", "Cel link requires the same Layer", "destination")
    end
    if dest_layer:cel(destination_number) ~= nil then
      return reject("cel_already_exists", "Destination Cel already exists", "destination")
    end
  elseif operation == "unlink" and #cel.affected(open_sprite, source_cel.image) < 2 then
    return reject("cel_unsupported_target", "Cel is not linked", "target")
  end
  local before, refused = affected_before(open_sprite, layer, path, number)
  if refused then
    refused.rejection.role = role
    return refused
  end
  if dest_layer then
    before[#before + 1] = cel.inspect(open_sprite, dest_layer, dest_path, destination_number)
  end
  sort_states(before)
  local original_count = #open_sprite.cels
  local source_image_digest = digest.fnv1a64(source_cel.image.bytes)
  app.transaction(operation .. " Cel", function()
    if operation == "set" then
      local changes = payload.changes
      if changes.position ~= nil then
        source_cel.position = Point(changes.position.x, changes.position.y)
      end
      if changes.opacity ~= nil then source_cel.opacity = changes.opacity end
      if changes.z_index ~= nil then source_cel.zIndex = changes.z_index end
    elseif operation == "copy" then
      local duplicate =
        open_sprite:newCel(dest_layer, destination_number, source_cel.image, source_cel.position)
      duplicate.opacity = source_cel.opacity
      duplicate.zIndex = source_cel.zIndex
      assert(duplicate.image ~= source_cel.image, "Cel copy retained shared Image")
      assert(
        digest.fnv1a64(duplicate.image.bytes) == source_image_digest,
        "Cel copy changed pixels"
      )
    elseif operation == "link" then
      apply_link(open_sprite, layer, number, destination_number)
    else
      app.activeSprite = open_sprite
      app.activeLayer = layer
      app.activeFrame = open_sprite.frames[number]
      app.range:clear()
      app.command.UnlinkCel()
    end
  end)
  local selected_layer, selected_path = dest_layer or layer, dest_path or path
  local selected_number = destination_number or number
  local selected = assert(selected_layer:cel(selected_number), "target Cel disappeared")
  local after = cel.inspect(open_sprite, selected_layer, selected_path, selected_number)
  local expected_count = original_count + (dest_layer and 1 or 0)
  assert(#open_sprite.cels == expected_count, "Cel operation changed unexpected Cel count")
  local affected = {}
  local seen = {}
  for _, state in ipairs(before) do
    local id = key(state)
    if not seen[id] then
      local current_layer =
        assert(selection.resolve(open_sprite, { layer_path = state.layer_path }, {})).layer
      affected[#affected + 1] =
        cel.inspect(open_sprite, current_layer, state.layer_path, state.frame_number)
      seen[id] = true
    end
  end
  assert(after.exists, "target Cel is absent")
  if operation == "link" then
    assert(selected.image == layer:cel(number).image, "Cel link did not share Image")
  elseif operation == "unlink" then
    assert(#after.linked_cels == 0, "Cel unlink retained shared Image")
    assert(digest.fnv1a64(selected.image.bytes) == source_image_digest, "Cel unlink changed pixels")
  elseif operation == "copy" then
    assert(#after.linked_cels == 0, "Cel copy retained shared Image")
  else
    assert(digest.fnv1a64(selected.image.bytes) == source_image_digest, "Cel set changed pixels")
  end
  sort_states(affected)
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
    before_cel_count = original_count,
    before_cels = before,
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
