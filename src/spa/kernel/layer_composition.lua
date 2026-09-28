-- Native composition over the original Layer tree; no flattening or pixel engine.
local module = {}
local palettes = dofile(app.params.effective_palette)

local function swap_indexes(bytes, mask)
  return (
    bytes:gsub(".", function(value)
      local index = value:byte()
      return string.char(index == 0 and mask or index == mask and 0 or index)
    end)
  )
end

local function missing_palette_index(message)
  return { rejection = { code = "image_composition_unsupported", message = message } }
end

function module.missing_output_index(image, effective)
  for pixel in image:pixels() do
    local index = pixel()
    if index >= #effective then
      return missing_palette_index(
        "Requested Frame Effective Palette has no output Palette Index " .. index
      )
    end
  end
end

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
  local mask = sprite.transparentColor
  local needs_zero_mask = output_color_mode == "preserve"
    and sprite.colorMode == ColorMode.INDEXED
    and mask ~= 0
  local effective
  if needs_zero_mask then
    effective = palettes.resolve(sprite, frame_number)
    if effective == nil then
      return nil, nil, missing_palette_index("Requested Frame has no Effective Palette")
    end
    if mask >= #effective then
      return nil,
        nil,
        missing_palette_index("Requested Frame Effective Palette has no Transparent Color Index")
    end
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
  local changed_images, changed_palettes, seen = {}, {}, {}
  local mask_changed, output_rejection = false, nil
  local ok, result = pcall(function()
    app.preferences.experimental.compose_groups = true
    for _, record in ipairs(records) do
      if composition.mode == "include" then
        record.layer.isVisible = included[record.key] == true
      end
      if included[record.key] then resolved[#resolved + 1] = record.path end
    end
    local original_spec = sprite.spec
    if needs_zero_mask then
      local function swap_image(image)
        if seen[image.id] then return end
        seen[image.id] = true
        changed_images[#changed_images + 1] = { image = image, bytes = image.bytes }
        image.bytes = swap_indexes(image.bytes, mask)
      end
      for _, cel in ipairs(sprite.cels) do
        if not cel.layer.isTilemap then swap_image(cel.image) end
      end
      for tileset_index = 1, #sprite.tilesets do
        local tileset = sprite.tilesets[tileset_index]
        for index = 0, #tileset - 1 do
          swap_image(tileset:tile(index).image)
        end
      end
      for palette_index = 1, #sprite.palettes do
        local palette = sprite.palettes[palette_index]
        if mask < #palette then
          local zero, transparent = palette:getColor(0), palette:getColor(mask)
          changed_palettes[#changed_palettes + 1] = {
            palette = palette,
            zero = zero,
            transparent = transparent,
          }
          palette:setColor(0, transparent)
          palette:setColor(mask, zero)
        end
      end
      sprite.transparentColor = 0
      mask_changed = true
    end
    local spec = sprite.spec
    spec.width, spec.height = area.width, area.height
    if output_color_mode == "rgb" then
      -- Select the native rendering path before composition; Source stays intact.
      spec.colorMode, spec.transparentColor = ColorMode.RGB, 0
    end
    local image = Image(spec)
    image:drawSprite(sprite, frame_number, -area.x, -area.y)
    if needs_zero_mask then
      original_spec.width, original_spec.height = area.width, area.height
      local restored = Image(original_spec)
      restored.bytes = swap_indexes(image.bytes, mask)
      image = restored
      output_rejection = module.missing_output_index(image, effective)
    end
    return image
  end)
  if mask_changed then sprite.transparentColor = mask end
  for index = #changed_palettes, 1, -1 do
    local change = changed_palettes[index]
    change.palette:setColor(0, change.zero)
    change.palette:setColor(mask, change.transparent)
  end
  for index = #changed_images, 1, -1 do
    local change = changed_images[index]
    change.image.bytes = change.bytes
  end
  for _, record in ipairs(records) do
    record.layer.isVisible = record.original_visible
  end
  app.preferences.experimental.compose_groups = previous_compose
  if not ok then error(result) end
  if output_rejection then return nil, nil, output_rejection end
  return result, resolved, nil
end

return module
