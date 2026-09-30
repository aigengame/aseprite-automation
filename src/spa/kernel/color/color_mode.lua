-- Color and Palette owns native conversion on an attached Sprite, without publication.
local module = {}
local palettes = dofile(app.params.palette)
local effective = dofile(app.params.effective_palette)
local layers = dofile(app.params.layer_select)
local digest = dofile(app.params.digest)
local null = json.decode("null")
local modes =
  { [ColorMode.RGB] = "rgb", [ColorMode.GRAY] = "grayscale", [ColorMode.INDEXED] = "indexed" }
local formats = { rgb = "rgb", grayscale = "gray", indexed = "indexed" }

function module.observe(sprite)
  local images, cels, tilesets, seen = {}, {}, {}, {}
  local function image_facts(image, kind, frame)
    if seen[image.id] then return seen[image.id] end
    local number = #images + 1
    seen[image.id] = number
    local palette_frame = null
    if frame then
      local _palette, change = effective.resolve(sprite, frame)
      palette_frame = change
    end
    local indexes = null
    if image.colorMode == ColorMode.INDEXED then
      local counts = {}
      for pixel in image:pixels() do
        local value = pixel()
        counts[value] = (counts[value] or 0) + 1
      end
      indexes = {}
      for index, count in pairs(counts) do
        indexes[#indexes + 1] = { index = index, pixel_count = count }
      end
      table.sort(indexes, function(a, b) return a.index < b.index end)
    end
    images[number] = {
      image_number = number,
      kind = kind,
      width = image.width,
      height = image.height,
      bytes_per_pixel = image.bytesPerPixel,
      row_stride = image.rowStride,
      content = digest.fnv1a64(image.bytes),
      conversion_frame_number = frame or null,
      palette_frame_number = palette_frame,
      palette_indices = indexes,
    }
    return number
  end
  for _, cel in ipairs(sprite.cels) do
    local tilemap = cel.layer.isTilemap
    cels[#cels + 1] = {
      layer_path = layers.current_path(sprite, cel.layer),
      frame_number = cel.frame.frameNumber,
      image_number = image_facts(
        cel.image,
        tilemap and "tilemap" or "cel",
        not tilemap and cel.frame.frameNumber or nil
      ),
      opacity = cel.opacity,
      is_background = cel.layer.isBackground,
    }
  end
  for number, tileset in ipairs(sprite.tilesets) do
    local tiles = {}
    for index = 0, #tileset - 1 do
      tiles[#tiles + 1] = {
        tile_index = index,
        image_number = tileset:tile(index).image
            and image_facts(tileset:tile(index).image, "tile", 1)
          or null,
      }
    end
    tilesets[#tilesets + 1] = { tileset_number = number, name = tileset.name, tiles = tiles }
  end
  return {
    color_mode = assert(modes[sprite.colorMode]),
    transparent_color_index = sprite.transparentColor,
    palettes = palettes.list(sprite),
    images = images,
    cels = cels,
    tilesets = tilesets,
  }
end

function module.change(sprite, conversion)
  local before = module.observe(sprite)
  assert(
    before.color_mode == conversion.source_color_mode,
    "Source Color Mode differs from requested branch"
  )
  local target = conversion.target
  local changed = before.color_mode ~= target.color_mode
  local mapping, dithering = null, null
  local command = { ui = false, format = formats[target.color_mode], toGray = target.to_gray }
  if changed and target.color_mode == "indexed" then
    command.rgbmap = target.rgb_map_algorithm
    command.fitCriteria = target.color_best_fit_criteria
    -- Native Sprite::rgbMap resolves DEFAULT to Octree on the verified baseline.
    mapping = {
      requested_rgb_map_algorithm = target.rgb_map_algorithm,
      effective_rgb_map_algorithm = target.rgb_map_algorithm == "default" and "octree"
        or target.rgb_map_algorithm,
      color_best_fit_criteria = target.color_best_fit_criteria,
    }
    if target.dithering then
      command.dithering = target.dithering.algorithm
      command.ditheringFactor = target.dithering.dithering_factor
      dithering = {
        requested_algorithm = target.dithering.algorithm,
        effective_algorithm = target.dithering.algorithm,
        matrix = null,
        dithering_factor = target.dithering.dithering_factor or null,
      }
    end
  end
  if changed then
    app.activeSprite = sprite
    app.command.ChangePixelFormat(command)
    assert(
      modes[sprite.colorMode] == target.color_mode,
      "Native conversion did not change Color Mode"
    )
  end
  return {
    source_color_mode = before.color_mode,
    target_color_mode = target.color_mode,
    changed = changed,
    to_gray = target.to_gray or null,
    mapping = mapping,
    dithering = dithering,
    before = before,
    after = module.observe(sprite),
  }
end

return module
