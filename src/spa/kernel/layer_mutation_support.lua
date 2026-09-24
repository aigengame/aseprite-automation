-- Exact Layer mutation, impact facts, and staged persistence verification.
local module = {}
local all_sections = { "frames", "tags", "palettes", "layers", "cels", "slices", "tilesets" }
local result_sections = { "layers", "cels" }

local function copy_path(path, index)
  local result = {}
  for _, value in ipairs(path) do
    result[#result + 1] = value
  end
  if index ~= nil then result[#result + 1] = index end
  return result
end

local function records(sprite, digest)
  local ordered, by_id = {}, {}
  local function visit(layers, prefix, parent_id)
    for index, layer in ipairs(layers) do
      local path = copy_path(prefix, index)
      local children = {}
      if layer.isGroup then
        for _, child in ipairs(layer.layers) do
          children[#children + 1] = child.id
        end
      end
      local cels, cel_facts = {}, {}
      for _, cel in ipairs(sprite.cels) do
        if cel.layer.id == layer.id then
          local frame_number = cel.frameNumber
          local bounds = cel.bounds
          cels[#cels + 1] = frame_number
          if digest ~= nil then
            cel_facts[frame_number] = table.concat({
              bounds.x,
              bounds.y,
              bounds.width,
              bounds.height,
              cel.opacity,
              cel.zIndex,
              cel.image.width,
              cel.image.height,
              digest.fnv1a64(cel.image.bytes),
            }, ":")
          end
        end
      end
      local record = {
        id = layer.id,
        path = path,
        parent_id = parent_id,
        children = children,
        cels = cels,
        cel_facts = cel_facts,
        name = layer.name,
        is_visible = layer.isVisible,
        is_editable = layer.isEditable,
        opacity = layer.opacity,
        blend_mode = layer.blendMode,
      }
      ordered[#ordered + 1] = record
      by_id[layer.id] = record
      if layer.isGroup then visit(layer.layers, path, layer.id) end
    end
  end
  visit(sprite.layers, {}, nil)
  return ordered, by_id
end

local function equal_array(left, right)
  if #left ~= #right then return false end
  for index = 1, #left do
    if left[index] ~= right[index] then return false end
  end
  return true
end

local function record_changed(left, right)
  if left == nil or right == nil then return true end
  if
    not equal_array(left.path, right.path)
    or left.parent_id ~= right.parent_id
    or not equal_array(left.children, right.children)
    or not equal_array(left.cels, right.cels)
    or left.name ~= right.name
    or left.is_visible ~= right.is_visible
    or left.is_editable ~= right.is_editable
    or left.opacity ~= right.opacity
    or left.blend_mode ~= right.blend_mode
  then
    return true
  end
  for _, frame_number in ipairs(left.cels) do
    if left.cel_facts[frame_number] ~= right.cel_facts[frame_number] then return true end
  end
  return false
end

local function affected(ordered, other, marked_layers, marked_cels)
  local result = { layer_paths = {}, cels = {} }
  for _, record in ipairs(ordered) do
    local counterpart = other[record.id]
    if marked_layers[record.id] or record_changed(record, counterpart) then
      result.layer_paths[#result.layer_paths + 1] = record.path
    end
    for _, frame_number in ipairs(record.cels) do
      if
        marked_cels[record.id]
        or counterpart == nil
        or not equal_array(record.path, counterpart.path)
        or record.cel_facts[frame_number] ~= counterpart.cel_facts[frame_number]
      then
        result.cels[#result.cels + 1] = {
          layer_path = record.path,
          frame_number = frame_number,
        }
      end
    end
  end
  return result
end

local function mark_subtree(layer, marked)
  marked[layer.id] = true
  if layer.isGroup then
    for _, child in ipairs(layer.layers) do
      mark_subtree(child, marked)
    end
  end
end

local function mark_set_impacts(layer, properties, inspection, marked_layers, marked_cels)
  local visible = properties.is_visible ~= nil and properties.is_visible ~= layer.isVisible
  local editable = properties.is_editable ~= nil and properties.is_editable ~= layer.isEditable
  if layer.isGroup and (visible or editable) then
    -- Effective visibility and editability follow the Group hierarchy.
    mark_subtree(layer, marked_layers)
    mark_subtree(layer, marked_cels)
  elseif
    visible
    or editable
    or (properties.opacity ~= nil and properties.opacity ~= layer.opacity)
    or (
      properties.blend_mode ~= nil
      and inspection.blend_mode_constant(properties.blend_mode) ~= layer.blendMode
    )
  then
    marked_cels[layer.id] = true
  end
end

local function is_regular(layer)
  return layer.isGroup
    or (
      layer.isImage
      and layer.isTransparent
      and not layer.isTilemap
      and not layer.isReference
      and not layer.isBackground
    )
end

local function is_regular_image(layer)
  return layer.isImage
    and layer.isTransparent
    and not layer.isTilemap
    and not layer.isReference
    and not layer.isBackground
    and not layer.isGroup
end

local function subtree_has_tilemap(layer)
  if layer.isTilemap then return true end
  if layer.isGroup then
    for _, child in ipairs(layer.layers) do
      if subtree_has_tilemap(child) then return true end
    end
  end
  return false
end

local function rejection(code, message) return { rejection = { code = code, message = message } } end

local function prevalidate(sprite, selected, payload, inspection)
  local operation, layer = payload.operation, selected.layer
  if operation == "set" then
    if not is_regular(layer) then
      return rejection(
        "layer_unsupported_target",
        "Layer set requires a regular Transparent Image or Group"
      )
    end
    local properties = payload.properties
    if type(properties) ~= "table" and type(properties) ~= "userdata" then
      return rejection("layer_unsupported_target", "Layer set requires properties")
    end
    local has_property = false
    for key, value in pairs(properties) do
      has_property = true
      if key == "name" then
        if type(value) ~= "string" or value == "" then
          return rejection("layer_unsupported_target", "Layer name must be nonempty")
        end
      elseif key == "is_visible" or key == "is_editable" then
        if type(value) ~= "boolean" then
          return rejection("layer_unsupported_target", key .. " must be Boolean")
        end
      elseif key == "opacity" then
        if
          not is_regular_image(layer)
          or type(value) ~= "number"
          or value % 1 ~= 0
          or value < 0
          or value > 255
        then
          return rejection(
            "layer_unsupported_target",
            "opacity requires a regular Image and 0..255"
          )
        end
      elseif key == "blend_mode" then
        if not is_regular_image(layer) or inspection.blend_mode_constant(value) == nil then
          return rejection(
            "layer_unsupported_target",
            "blend_mode requires a regular Image and supported mode"
          )
        end
      else
        return rejection(
          "layer_unsupported_target",
          "unsupported Layer property: " .. tostring(key)
        )
      end
    end
    if not has_property then
      return rejection("layer_unsupported_target", "Layer set requires properties")
    end
  elseif operation == "move" then
    if not is_regular(layer) then
      return rejection(
        "layer_unsupported_target",
        "Layer move requires a regular Transparent Image or Group"
      )
    end
    local siblings = layer.parent == sprite and sprite.layers or layer.parent.layers
    local index = payload.stack_index
    if type(index) ~= "number" or index % 1 ~= 0 or index < 1 or index > #siblings then
      return rejection("layer_invalid_position", "stack_index is outside the current parent")
    end
    for position = math.min(layer.stackIndex, index), math.max(layer.stackIndex, index) do
      local crossed = siblings[position]
      if crossed ~= layer and not is_regular(crossed) then
        return rejection(
          "layer_invalid_position",
          "Layer move would change the stack position of an unsupported sibling"
        )
      end
    end
  elseif operation == "remove" then
    if subtree_has_tilemap(layer) then
      return rejection("layer_unsupported_target", "Layer remove cannot delete a Tilemap subtree")
    end
  elseif operation == "merge" then
    if not is_regular_image(layer) then
      return rejection(
        "layer_unsupported_target",
        "Merge source must be a regular Transparent Image"
      )
    end
    local siblings = layer.parent == sprite and sprite.layers or layer.parent.layers
    local lower = siblings[layer.stackIndex - 1]
    if lower == nil or not is_regular_image(lower) then
      return rejection(
        "layer_unsupported_target",
        "Merge requires the immediate lower regular Transparent Image sibling"
      )
    end
    return nil, lower
  else
    return rejection("layer_unsupported_target", "unsupported Layer operation")
  end
  return nil, nil
end

local function render_digests(sprite, digest)
  local previous_compose_groups = app.preferences.experimental.compose_groups
  local ok, result = pcall(function()
    app.preferences.experimental.compose_groups = true
    local digests = {}
    for frame_number = 1, #sprite.frames do
      local image = Image(sprite.spec)
      image:drawSprite(sprite, frame_number, 0, 0)
      digests[frame_number] = digest.fnv1a64(image.bytes)
    end
    return digests
  end)
  pcall(function() app.preferences.experimental.compose_groups = previous_compose_groups end)
  if not ok then error(result) end
  return result
end

local function apply(sprite, payload, layer, lower, inspection)
  if payload.operation == "set" then
    app.transaction("Set Layer", function()
      local properties = payload.properties
      if properties.name ~= nil then layer.name = properties.name end
      if properties.is_visible ~= nil then layer.isVisible = properties.is_visible end
      if properties.is_editable ~= nil then layer.isEditable = properties.is_editable end
      if properties.opacity ~= nil then layer.opacity = properties.opacity end
      if properties.blend_mode ~= nil then
        layer.blendMode = inspection.blend_mode_constant(properties.blend_mode)
      end
    end)
    local properties = payload.properties
    if properties.name ~= nil then
      assert(layer.name == properties.name, "native Layer name differs")
    end
    if properties.is_visible ~= nil then
      assert(layer.isVisible == properties.is_visible, "native Layer visibility differs")
    end
    if properties.is_editable ~= nil then
      assert(layer.isEditable == properties.is_editable, "native Layer editability differs")
    end
    if properties.opacity ~= nil then
      assert(layer.opacity == properties.opacity, "native Layer opacity differs")
    end
    if properties.blend_mode ~= nil then
      assert(
        layer.blendMode == inspection.blend_mode_constant(properties.blend_mode),
        "native Layer blend mode differs"
      )
    end
  elseif payload.operation == "move" then
    app.transaction("Move Layer", function() layer.stackIndex = payload.stack_index end)
    assert(layer.stackIndex == payload.stack_index, "native Layer move did not reach stack_index")
  elseif payload.operation == "remove" then
    local removed_id = layer.id
    app.transaction("Remove Layer", function() sprite:deleteLayer(layer) end)
    local _, current = records(sprite)
    assert(current[removed_id] == nil, "native Layer remove retained its target")
  else
    local source_id, lower_id = layer.id, lower.id
    local previous_blend = app.preferences.experimental.new_blend
    local ok, failure = pcall(function()
      app.preferences.experimental.new_blend = true
      app.activeSprite = sprite
      app.activeLayer = layer
      app.activeFrame = sprite.frames[1]
      assert(app.command.MergeDownLayer(), "native Merge Down failed")
    end)
    pcall(function() app.preferences.experimental.new_blend = previous_blend end)
    if not ok then error(failure) end
    local _, current = records(sprite)
    assert(current[lower_id] ~= nil, "native Merge Down removed the lower Layer")
    assert(current[source_id] == nil, "native Merge Down retained the source Layer")
  end
end

function module.execute(payload, inspection, selection, digest, persistence)
  local open_sprite = nil
  local previous = { sprite = app.activeSprite, layer = app.activeLayer, frame = app.activeFrame }
  local ok, result = pcall(function()
    open_sprite = assert(app.open(payload.source_sprite_file), "could not open Source Sprite File")
    local verified_uuids = inspection.saved_layer_uuids(open_sprite, payload.source_sprite_file)
    local selected, code, message = selection.resolve(open_sprite, payload.target, verified_uuids)
    if selected == nil then return rejection(code, message) end
    local invalid, lower = prevalidate(open_sprite, selected, payload, inspection)
    if invalid ~= nil then return invalid end
    local before = inspection.inspect(open_sprite, result_sections, verified_uuids)
    local before_ordered, before_by_id = records(open_sprite, digest)
    local source_uuids = {}
    for _, record in ipairs(before_ordered) do
      source_uuids[record.id] = verified_uuids[table.concat(record.path, "/")]
    end
    local marked_layers, marked_cels = {}, {}
    if payload.operation == "set" then
      mark_set_impacts(selected.layer, payload.properties, inspection, marked_layers, marked_cels)
    end
    local before_rendered = render_digests(open_sprite, digest)
    apply(open_sprite, payload, selected.layer, lower, inspection)
    local after_ordered, after_by_id = records(open_sprite, digest)
    local unsaved_uuids = {}
    for _, record in ipairs(after_ordered) do
      local uuid = source_uuids[record.id]
      if uuid ~= nil then unsaved_uuids[table.concat(record.path, "/")] = uuid end
    end
    local after_rendered = render_digests(open_sprite, digest)
    local before_affected = affected(before_ordered, after_by_id, marked_layers, marked_cels)
    local after_affected = affected(after_ordered, before_by_id, marked_layers, marked_cels)
    local rendered_frames = {}
    for number = 1, #open_sprite.frames do
      rendered_frames[number] = {
        frame_number = number,
        before_digest = before_rendered[number],
        after_digest = after_rendered[number],
      }
    end
    local unsaved =
      persistence.snapshot(open_sprite, inspection, digest, all_sections, unsaved_uuids)
    assert(open_sprite:saveAs(payload.staged_sprite_file), "could not save staged Sprite")
    open_sprite:close()
    open_sprite = assert(app.open(payload.staged_sprite_file), "could not reopen staged Sprite")
    verified_uuids = inspection.saved_layer_uuids(open_sprite, payload.staged_sprite_file)
    local persisted =
      persistence.snapshot(open_sprite, inspection, digest, all_sections, verified_uuids)
    persistence.assert_same(unsaved, persisted, "Layer")
    local persisted_rendered = render_digests(open_sprite, digest)
    for number = 1, #persisted_rendered do
      assert(
        persisted_rendered[number] == after_rendered[number],
        "persisted Layer rendering differs"
      )
    end
    local after = inspection.inspect(open_sprite, result_sections, verified_uuids)
    return {
      before = before,
      after = after,
      affected_before = before_affected,
      affected_after = after_affected,
      rendered_frames = rendered_frames,
      persisted_reopen_verified = true,
    }
  end)
  if open_sprite ~= nil then pcall(function() open_sprite:close() end) end
  if previous.sprite ~= nil and previous.sprite.isValid then
    pcall(function() app.activeSprite = previous.sprite end)
    pcall(function() app.activeLayer = previous.layer end)
    pcall(function() app.activeFrame = previous.frame end)
  end
  if not ok then error(result) end
  return result
end

return module
