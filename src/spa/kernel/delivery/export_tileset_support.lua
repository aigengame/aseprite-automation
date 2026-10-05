-- Delivery projects native Tile facts into one uniform atlas and normalized map.
local module = {}
local tilesets = dofile(app.params.tilesets)
local keys = dofile(app.params.tile_keys)
local tilemaps = dofile(app.params.tilemaps)
local tile_inspection = dofile(app.params.tile_inspection)
local inspection = dofile(app.params.inspection)
local palettes = dofile(app.params.effective_palette)
local profiles = dofile(app.params.color_profile)
local images = dofile(app.params.export_image_support)
local digest = dofile(app.params.digest)
local null = json.decode("null")

local function reject(reason, message)
  return { rejection = { code = "tileset_export_unsupported", reason = reason, message = message } }
end

local function integer(value, minimum, maximum)
  local number = tonumber(value)
  if not number or number % 1 ~= 0 or number < minimum or number > maximum then return nil end
  return math.tointeger(number)
end

local function profile(sprite, path)
  local ok, observed = pcall(profiles.restore_file_profile, sprite, path)
  if not ok then return nil, reject("color_profile", "Source Color Profile cannot be preserved") end
  if
    observed.kind == "icc"
    and (observed.icc_identity == nil or sprite.colorMode == ColorMode.GRAY)
  then
    local mode = ({
      [ColorMode.RGB] = "RGB",
      [ColorMode.GRAY] = "Grayscale",
      [ColorMode.INDEXED] = "Indexed",
    })[sprite.colorMode]
    return nil,
      reject(
        "color_profile",
        mode
          .. " with ICC Profile "
          .. (observed.icc_identity or "outside the supported set")
          .. " cannot be preserved"
      )
  end
  if observed.kind ~= "none" and observed.kind ~= "srgb" and observed.kind ~= "icc" then
    return nil, reject("color_profile", "Unsupported Source Color Profile")
  end
  return { kind = observed.kind, icc_identity = observed.icc_identity or null }
end

local function palette_facts(sprite, frame, tileset)
  if sprite.colorMode ~= ColorMode.INDEXED then return nil, null end
  local palette, change = palettes.resolve(sprite, frame)
  if palette == nil or #palette < 1 or #palette > 256 then
    return nil,
      nil,
      reject("palette_capacity", "Indexed PNG requires 1–256 Effective Palette entries")
  end
  if sprite.transparentColor < 0 or sprite.transparentColor >= #palette then
    return nil,
      nil,
      reject("palette_incomplete", "Effective Palette omits the Transparent Color Index")
  end
  for index = 0, #tileset - 1 do
    for pixel in tileset:tile(index).image:pixels() do
      if pixel() >= #palette then
        return nil,
          nil,
          reject("palette_incomplete", "Effective Palette omits an exported Tile pixel index")
      end
    end
  end
  local entries = {}
  for index = 0, #palette - 1 do
    local color = palette:getColor(index)
    entries[#entries + 1] = {
      red = color.red,
      green = color.green,
      blue = color.blue,
      alpha = index == sprite.transparentColor and 0 or color.alpha,
    }
  end
  return palette,
    {
      frame_number = frame,
      palette_frame_number = change,
      transparent_color_index = sprite.transparentColor,
      entries = entries,
    }
end

local function prepare(sprite, payload)
  local uuids = inspection.saved_layer_uuids(sprite, payload.source_sprite_file)
  local tileset, index, failure = tilesets.resolve_tileset(sprite, payload.tileset, uuids)
  if failure then return nil, failure end
  local layer
  layer, failure = tilesets.resolve_layer(sprite, payload.target.layer, uuids)
  if failure then return nil, failure end
  if layer.tileset ~= tileset then
    return nil,
      reject(
        "tileset_binding_mismatch",
        "Selected Tilemap Layer must reference the selected Tileset"
      )
  end
  local frame = integer(payload.target.frame_number, 1, #sprite.frames)
  if not frame then
    return nil,
      {
        rejection = {
          code = "tilemap_frame_out_of_bounds",
          message = "Frame is outside the Sprite timeline",
        },
      }
  end
  local cel = layer:cel(frame)
  if not cel then
    return nil,
      {
        rejection = { code = "tilemap_cel_missing", message = "The selected Tilemap Cel is absent" },
      }
  end
  local area
  area, failure = tile_inspection.rectangle(cel.image, payload.rectangle)
  if failure then return nil, failure end
  local mode = ({
    [ColorMode.RGB] = "rgb",
    [ColorMode.GRAY] = "grayscale",
    [ColorMode.INDEXED] = "indexed",
  })[sprite.colorMode]
  if not mode then return nil, reject("color_mode", "Unsupported Source Color Mode") end
  local observed_profile
  observed_profile, failure = profile(sprite, payload.source_sprite_file)
  if failure then return nil, failure end
  local columns = integer(payload.columns, 1, math.maxinteger)
  if not columns then
    return nil, reject("atlas_layout", "Atlas columns must be a positive integer")
  end
  local grid = tileset.grid.tileSize
  local max_dimension = 0x7fffffff
  local dimension_range = "Atlas width and height must each be within 1.."
    .. max_dimension
    .. " pixels"
  if grid.width < 1 or grid.height < 1 or columns > max_dimension // grid.width then
    return nil, reject("atlas_layout", dimension_range)
  end
  local width, height = columns * grid.width, ((#tileset - 1) // columns + 1) * grid.height
  if width < 1 or height < 1 or width > max_dimension or height > max_dimension then
    return nil, reject("atlas_layout", dimension_range)
  end
  -- Tile Authoring supplies native Findings; this export requires all of them clear.
  local findings = tile_inspection.key_findings(tileset, index)
  if #findings > 0 then
    return nil, reject(findings[1].code, "Tileset identity or Tile Image Grid is invalid")
  end
  local tile_entries, digests = {}, {}
  for tile_index = 0, #tileset - 1 do
    local tile = tileset:tile(tile_index)
    if tile.image.colorMode ~= sprite.colorMode then
      return nil,
        reject("tile_image_grid_mismatch", "Every Tile Image must match the Source Color Mode")
    end
    local entry = {
      kind = tile_index == 0 and "empty" or "tile",
      tile_index = tile_index,
      rectangle = {
        x = (tile_index % columns) * grid.width,
        y = (tile_index // columns) * grid.height,
        width = grid.width,
        height = grid.height,
      },
    }
    if tile_index > 0 then entry.tile_key = keys.observe(tile) end
    tile_entries[#tile_entries + 1] = entry
    digests[#digests + 1] = digest.fnv1a64(tile.image.bytes)
  end
  local pc = app.pixelColor
  local allowed_flags = pc.TILE_XFLIP | pc.TILE_YFLIP | pc.TILE_DFLIP
  for y = area.y, area.y + area.height - 1 do
    for x = area.x, area.x + area.width - 1 do
      local packed = cel.image:getPixel(x, y)
      local finding, ti = tile_inspection.cell_finding(tileset, packed)
      local flags = pc.tileF(packed)
      if finding or (flags & ~allowed_flags) ~= 0 or (ti | flags) ~= packed then
        return nil,
          reject(
            "placement_invalid",
            "Tile Region contains an invalid Tile Index or unsupported transform flags"
          )
      end
    end
  end
  local palette, encoded_palette
  palette, encoded_palette, failure = palette_facts(sprite, frame, tileset)
  if failure then return nil, failure end
  local metadata = {
    schema_version = 1,
    source_sprite_file = payload.source_sprite_file,
    tileset = tilesets.facts(sprite, tileset, index, uuids),
    tilemap = tilemaps.cel_facts(sprite, layer, frame, uuids),
    snapshot = tile_inspection.region(cel.image, tileset, area),
    atlas = {
      path = payload.image_path,
      width = width,
      height = height,
      columns = columns,
      color_mode = mode,
      profile = observed_profile,
      palette = encoded_palette,
      tiles = tile_entries,
    },
  }
  return { tileset = tileset, palette = palette, metadata = metadata, tile_digests = digests }
end

local function png_encoding(path)
  local file = assert(io.open(path, "rb"))
  local header = assert(file:read(33))
  file:close()
  assert(
    #header == 33 and header:sub(1, 8) == "\137PNG\13\10\26\10",
    "Native output has no PNG IHDR"
  )
  local _, _, depth, color_type = string.unpack(">I4I4BB", header, 17)
  return { bit_depth = depth, color_type = color_type }
end

function module.execute(payload)
  local previous = { sprite = app.activeSprite, layer = app.activeLayer, frame = app.activeFrame }
  local sprite
  local ok, result = pcall(function()
    sprite = assert(app.open(payload.source_sprite_file), "Could not open Source Sprite File")
    local context, failure = prepare(sprite, payload)
    if failure then return failure end
    local atlas_facts = context.metadata.atlas
    local spec = sprite.spec
    spec.width, spec.height = atlas_facts.width, atlas_facts.height
    spec.colorSpace = sprite.colorSpace
    spec.transparentColor = sprite.colorMode == ColorMode.INDEXED and sprite.transparentColor or 0
    local atlas = assert(Image(spec), "Could not allocate atlas Image")
    assert(
      atlas.width == spec.width
        and atlas.height == spec.height
        and atlas.colorMode == sprite.colorMode,
      "Native atlas Image differs from requested dimensions or Color Mode"
    )
    app.activeSprite = sprite
    for _, entry in ipairs(atlas_facts.tiles) do
      atlas:drawImage(
        context.tileset:tile(entry.tile_index).image,
        entry.rectangle.x,
        entry.rectangle.y,
        255,
        BlendMode.SRC
      )
    end
    images.encode_image(atlas, payload.staged_png_file, context.palette)
    atlas_facts.png = png_encoding(payload.staged_png_file)
    local file = assert(io.open(payload.staged_metadata_file, "wb"))
    assert(file:write(json.encode(context.metadata)))
    assert(file:close())
    return { metadata = context.metadata, tile_digests = context.tile_digests }
  end)
  if sprite ~= nil then pcall(function() sprite:close() end) end
  if previous.sprite ~= nil and previous.sprite.isValid then
    app.activeSprite, app.activeLayer, app.activeFrame =
      previous.sprite, previous.layer, previous.frame
  end
  if not ok then error(result) end
  return result
end

return module
