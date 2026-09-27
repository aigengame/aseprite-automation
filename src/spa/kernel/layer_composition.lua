-- Native composition over the original Layer tree; no flattening or pixel engine.
local module = {}

local function copy_path(path)
  local result = {}
  for _, value in ipairs(path) do
    result[#result + 1] = value
  end
  return result
end

local function layers_at(layers, prefix, ancestor_visible, result)
  for index, layer in ipairs(layers) do
    local path = copy_path(prefix)
    path[#path + 1] = index
    local visible = ancestor_visible and layer.isVisible
    result[#result + 1] = {
      layer = layer,
      path = path,
      key = table.concat(path, "/"),
      original_visible = layer.isVisible,
      visible = visible,
    }
    if layer.isGroup then layers_at(layer.layers, path, visible, result) end
  end
end

function module.copy(value)
  if value.mode == "visible" then return { mode = "visible" } end
  local layers = {}
  for _, address in ipairs(value.layers) do
    layers[#layers + 1] = address.layer_path and { layer_path = copy_path(address.layer_path) }
      or address.layer_name and { layer_name = address.layer_name }
      or { layer_uuid = address.layer_uuid }
  end
  return { mode = "include", layers = layers }
end

function module.render(sprite, frame_number, composition, area, selection, uuids, output_color_mode)
  assert(output_color_mode == "preserve" or output_color_mode == "rgb", "invalid output Color Mode")
  if
    output_color_mode == "preserve"
    and sprite.colorMode == ColorMode.INDEXED
    and sprite.transparentColor ~= 0
  then
    return nil,
      nil,
      {
        rejection = {
          code = "image_composition_unsupported",
          message = "Native preserve-Indexed composition cannot retain a nonzero transparent index; "
            .. "request rgb for a derived visual observation or individual Get for stored indexes",
        },
      }
  end
  local records, included = {}, {}
  layers_at(sprite.layers, {}, true, records)
  if composition.mode == "include" then
    for index, address in ipairs(composition.layers) do
      local selected, code, message = selection.resolve(sprite, address, uuids)
      if selected == nil then
        return nil, nil, { rejection = { code = code, message = message, selector_number = index } }
      end
      local key = table.concat(selected.path, "/")
      included[key] = true
      if selected.layer.isGroup then
        for _, record in ipairs(records) do
          if record.key:sub(1, #key + 1) == key .. "/" then included[record.key] = true end
        end
      end
    end
    -- Ancestors supply compositing context, without enabling sibling branches.
    for _, record in ipairs(records) do
      if included[record.key] then
        local path = copy_path(record.path)
        while #path > 1 do
          table.remove(path)
          included[table.concat(path, "/")] = true
        end
      end
    end
  else
    assert(composition.mode == "visible", "unsupported Layer Composition")
    for _, record in ipairs(records) do
      included[record.key] = record.visible
    end
  end
  local previous_compose = app.preferences.experimental.compose_groups
  local resolved = {}
  local ok, result = pcall(function()
    app.preferences.experimental.compose_groups = true
    for _, record in ipairs(records) do
      if composition.mode == "include" then
        record.layer.isVisible = included[record.key] == true
      end
      if included[record.key] then resolved[#resolved + 1] = record.path end
    end
    local spec = sprite.spec
    spec.width, spec.height = area.width, area.height
    if output_color_mode == "rgb" then
      -- Select the native rendering path before composition; Source stays intact.
      spec.colorMode, spec.transparentColor = ColorMode.RGB, 0
    end
    local image = Image(spec)
    image:drawSprite(sprite, frame_number, -area.x, -area.y)
    return image
  end)
  for _, record in ipairs(records) do
    record.layer.isVisible = record.original_visible
  end
  app.preferences.experimental.compose_groups = previous_compose
  if not ok then error(result) end
  return result, resolved, nil
end

return module
