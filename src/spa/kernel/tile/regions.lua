-- Tilemap region policy: resolve every target and Key before replacing one shared Image.
local module = {}
local tilesets = dofile(app.params.tilesets)
local keys = dofile(app.params.tile_keys)
local cels = dofile(app.params.cel)
local tilemaps = dofile(app.params.tilemaps)
local digest = dofile(app.params.digest)
local persistence = dofile(app.params.persistence)
local colors = dofile(app.params.raster_color)
local palettes = dofile(app.params.effective_palette)
local function reject(code, message) return { rejection = { code = code, message = message } } end
local function integer(value, minimum, maximum)
  local number = tonumber(value)
  if not number or number % 1 ~= 0 or number < minimum or number > maximum then return nil end
  return math.tointeger(number)
end

local function packed_placement(tileset, placement, resolved)
  if placement.kind == "empty" then return 0 end
  local index = resolved[placement.tile_key]
  if not index then
    local failure
    index, failure = keys.resolve(tileset, placement.tile_key)
    if failure then
      failure.rejection.tile_key = placement.tile_key
      return nil, failure
    end
    resolved[placement.tile_key] = index
  end
  local packed = index
  if placement.flip_x then packed = packed | app.pixelColor.TILE_XFLIP end
  if placement.flip_y then packed = packed | app.pixelColor.TILE_YFLIP end
  if placement.flip_diagonal then packed = packed | app.pixelColor.TILE_DFLIP end
  return packed
end

-- Creation Palette basis is not a binding: use every actual shared Cel Frame.
local function placement_palettes(sprite, tileset, resolved, affected)
  local written, used = {}, {}
  for key, index in pairs(resolved) do
    local indexes = {}
    if sprite.colorMode == ColorMode.INDEXED then
      local seen = {}
      for pixel in tileset:tile(index).image:pixels() do
        seen[pixel()] = true
      end
      for value in pairs(seen) do
        indexes[#indexes + 1] = value
        used[value] = true
      end
      table.sort(indexes)
    end
    written[#written + 1] = { tile_key = key, tile_index = index, palette_indexes = indexes }
  end
  table.sort(written, function(left, right) return left.tile_index < right.tile_index end)
  if sprite.colorMode ~= ColorMode.INDEXED or #written == 0 then return written, {} end
  used[sprite.transparentColor] = true
  local checked = {}
  for _, cel in ipairs(affected) do
    if not checked[cel.frame_number] then
      checked[cel.frame_number] = true
      local palette, change = palettes.resolve(sprite, cel.frame_number)
      assert(palette, "Indexed Sprite has no Effective Palette")
      local missing = {}
      for index in pairs(used) do
        if index >= #palette then missing[#missing + 1] = index end
      end
      table.sort(missing)
      if #missing > 0 then
        local failure = reject(
          "tilemap_region_invalid",
          "Written Tile indexes or Transparent Color Index are undefined in an affected Frame Palette"
        )
        local details = failure.rejection
        details.reason, details.frame_number = "palette_incompatible", cel.frame_number
        details.palette_frame_number, details.palette_size, details.undefined_indexes =
          change, #palette, missing
        return nil, nil, failure
      end
    end
  end
  return written, colors.palette_facts(sprite, affected, used)
end

function module.prepare(sprite, payload, uuids)
  local layer, failure = tilesets.resolve_layer(sprite, payload.target.layer, uuids)
  if failure then return nil, failure end
  local frame = integer(payload.target.frame_number, 1, #sprite.frames)
  if not frame then
    return nil, reject("tilemap_frame_out_of_bounds", "Frame is outside the Sprite timeline")
  end
  local cel = layer:cel(frame)
  if not cel then
    return nil, reject("tilemap_cel_missing", "The selected Tilemap Cel is absent")
  end
  if cel.image.width * cel.image.height > payload.operation_limits.tile_cells then
    local failed =
      reject("tilemap_region_invalid", "Tilemap Cel Image exceeds the tile_cells Operation Limit")
    failed.rejection.reason = "tile_cells_limit"
    return nil, failed
  end
  local x, y, width, height = 0, 0, cel.image.width, cel.image.height
  local rectangle = payload.snapshot and payload.snapshot.rectangle or payload.rectangle
  if rectangle then
    x, y = integer(rectangle.x, 0, width - 1), integer(rectangle.y, 0, height - 1)
    width, height = integer(rectangle.width, 1, width), integer(rectangle.height, 1, height)
    if
      not x
      or not y
      or not width
      or not height
      or x + width > cel.image.width
      or y + height > cel.image.height
    then
      return nil,
        reject("tile_region_out_of_bounds", "Tile Cell Rectangle is outside the Cel Image")
    end
  end
  local entries, resolved = {}, {}
  local input = payload.snapshot or payload.patch or { entries = {} }
  for _, entry in ipairs(input.entries) do
    local column, row =
      integer(entry.tile_x, x, x + width - 1), integer(entry.tile_y, y, y + height - 1)
    if not column or not row then
      return nil, reject("tile_region_out_of_bounds", "Explicit Tile Cell is outside the Cel Image")
    end
    local packed, rejected = packed_placement(layer.tileset, entry.placement, resolved)
    if rejected then return nil, rejected end
    entries[#entries + 1] = { x = column, y = row, value = packed }
  end
  local fill = 0
  if payload.placement then
    fill, failure = packed_placement(layer.tileset, payload.placement, resolved)
    if failure then return nil, failure end
  end
  local affected = cels.affected(sprite, cel.image)
  local written_tiles, effective_palettes, rejected =
    placement_palettes(sprite, layer.tileset, resolved, affected)
  if rejected then return nil, rejected end
  local final = Image(cel.image)
  if rectangle then
    for row = y, y + height - 1 do
      for column = x, x + width - 1 do
        final:putPixel(column, row, fill)
      end
    end
  end
  for _, entry in ipairs(entries) do
    final:putPixel(entry.x, entry.y, entry.value)
  end
  local changed = 0
  for row = 0, final.height - 1 do
    for column = 0, final.width - 1 do
      if final:getPixel(column, row) ~= cel.image:getPixel(column, row) then
        changed = changed + 1
      end
    end
  end
  return {
    cel = cel,
    frame = frame,
    layer = layer,
    image = final,
    before_digest = digest.fnv1a64(cel.image.bytes),
    changed = changed,
    written = rectangle and width * height or #entries,
    affected = affected,
    written_tiles = written_tiles,
    effective_palettes = effective_palettes,
  }
end

function module.apply(sprite, context)
  app.activeSprite = sprite
  app.transaction("Tilemap region", function() context.cel.image = context.image end)
  assert(
    context.cel.image.bytes == context.image.bytes,
    "Tilemap Image differs from prepared Cells"
  )
  local affected = cels.affected(sprite, context.cel.image)
  assert(#affected == #context.affected, "Tilemap write changed native Image sharing")
  for index, before in ipairs(context.affected) do
    local after = affected[index]
    -- Only content can change; placement, opacity, z-order, and complete links survive.
    before.content = after.content
    persistence.assert_equal(before, after, "Tilemap Cel")
  end
end

function module.observe(sprite, context, uuids, sprite_facts)
  local path = context.affected[1].layer_path
  local layer = sprite
  for _, index in ipairs(path) do
    layer = layer.layers[index]
  end
  local image = assert(layer:cel(context.affected[1].frame_number)).image
  assert(image.bytes == context.image.bytes, "Reopened Tilemap differs from prepared Cells")
  local selected = assert(tilesets.resolve_layer(sprite, { layer_path = context.path }, uuids))
  return {
    tilemap = tilemaps.cel_facts(sprite, selected, context.frame, uuids),
    affected_cels = cels.affected(sprite, image),
    cells_written = context.written,
    cells_changed = context.changed,
    before_content_digest = { algorithm = "fnv1a64", value = context.before_digest },
    after_content_digest = { algorithm = "fnv1a64", value = digest.fnv1a64(image.bytes) },
    written_tiles = context.written_tiles,
    effective_palettes = context.effective_palettes,
    sprite = sprite_facts,
    persisted_reopen_verified = true,
  }
end

return module
