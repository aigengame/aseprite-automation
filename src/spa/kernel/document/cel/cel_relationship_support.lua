-- Shared live Cel relationship semantics; persistence belongs to the enclosing handler.
local module = {}
local selection = dofile(app.params.layer_select)
local cel = dofile(app.params.cel)
local digest = dofile(app.params.digest)

local function reject(code, message, role)
  return { rejection = { code = code, message = message, role = role } }
end

local function resolve(sprite, address, uuids, role)
  local layer, path, refused = cel.resolve(sprite, address, selection, uuids)
  if refused then
    refused.rejection.role = role
    return nil, nil, refused
  end
  if not cel.is_regular_transparent(layer) then
    return nil,
      nil,
      reject("cel_unsupported_target", "Operation requires a regular Transparent Layer", role)
  end
  return layer, path, nil
end

local function key(state)
  local parts = {}
  for _, index in ipairs(state.layer_path) do
    parts[#parts + 1] = tostring(assert(math.tointeger(index)))
  end
  return table.concat(parts, "/") .. ":" .. tostring(assert(math.tointeger(state.frame_number)))
end

local function is_editable_hierarchy(layer, sprite)
  local current = layer
  while current ~= sprite do
    if not current.isEditable then return false end
    current = current.parent
  end
  return true
end

local function affected_before(sprite, layer, path, number)
  local target = layer:cel(number)
  if target == nil then return { cel.inspect(sprite, layer, path, number) } end
  local group = cel.affected(sprite, target.image)
  for _, state in ipairs(group) do
    local selected = selection.resolve(sprite, { layer_path = state.layer_path }, {})
    assert(selected ~= nil, "linked Cel Layer disappeared")
    if not cel.is_regular_transparent(selected.layer) then
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

function module.apply_live(sprite, operation, payload, uuids)
  assert(operation == "set" or operation == "copy" or operation == "link" or operation == "unlink")
  local primary = payload.source or payload.target
  local role = payload.source and "source" or "target"
  local layer, path, refused = resolve(sprite, primary, uuids, role)
  if refused then return refused end
  local number = primary.frame_number
  local source_cel = layer:cel(number)
  if source_cel == nil then return reject("cel_not_found", "Cel does not exist", role) end
  local dest_layer, dest_path, destination_number
  if payload.destination then
    dest_layer, dest_path, refused = resolve(sprite, payload.destination, uuids, "destination")
    if refused then return refused end
    destination_number = payload.destination.frame_number
    if operation == "link" and dest_layer ~= layer then
      return reject("cel_unsupported_target", "Cel link requires the same Layer", "destination")
    end
    if dest_layer:cel(destination_number) ~= nil then
      return reject("cel_already_exists", "Destination Cel already exists", "destination")
    end
  elseif operation == "unlink" then
    if #cel.affected(sprite, source_cel.image) < 2 then
      return reject("cel_unsupported_target", "Cel is not linked", "target")
    end
    if not is_editable_hierarchy(layer, sprite) then
      return reject(
        "cel_unsupported_target",
        "Cel unlink requires an editable Layer hierarchy",
        "target"
      )
    end
  end
  local before
  before, refused = affected_before(sprite, layer, path, number)
  if refused then
    refused.rejection.role = role
    return refused
  end
  if dest_layer then
    before[#before + 1] = cel.inspect(sprite, dest_layer, dest_path, destination_number)
  end
  cel.sort_states(before)
  local original_count = #sprite.cels
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
        sprite:newCel(dest_layer, destination_number, source_cel.image, source_cel.position)
      duplicate.opacity = source_cel.opacity
      duplicate.zIndex = source_cel.zIndex
      assert(duplicate.image ~= source_cel.image, "Cel copy retained shared Image")
      assert(
        digest.fnv1a64(duplicate.image.bytes) == source_image_digest,
        "Cel copy changed pixels"
      )
    elseif operation == "link" then
      apply_link(sprite, layer, number, destination_number)
    else
      app.activeSprite = sprite
      app.activeLayer = layer
      app.activeFrame = sprite.frames[number]
      app.range:clear()
      app.command.UnlinkCel()
    end
  end)
  local selected_layer, selected_path = dest_layer or layer, dest_path or path
  local selected_number = destination_number or number
  local selected = assert(selected_layer:cel(selected_number), "target Cel disappeared")
  local after = cel.inspect(sprite, selected_layer, selected_path, selected_number)
  local expected_count = original_count + (dest_layer and 1 or 0)
  assert(#sprite.cels == expected_count, "Cel operation changed unexpected Cel count")
  local affected = {}
  local seen = {}
  local target_id = key(after)
  for _, state in ipairs(before) do
    local id = key(state)
    if not seen[id] then
      local include = id == target_id
        or operation == "link"
        or operation == "unlink"
        or (operation == "set" and (payload.changes.position or payload.changes.opacity))
      if include then
        local current_layer =
          assert(selection.resolve(sprite, { layer_path = state.layer_path }, {})).layer
        affected[#affected + 1] =
          cel.inspect(sprite, current_layer, state.layer_path, state.frame_number)
      end
      seen[id] = true
    end
  end
  assert(after.exists, "target Cel is absent")
  assert(#affected > 0, "Cel operation lost affected target")
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
  cel.sort_states(affected)
  return {
    before_cel_count = original_count,
    before_cels = before,
    affected_cels = affected,
    cel = after,
  }
end

return module
