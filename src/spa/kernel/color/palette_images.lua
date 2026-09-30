-- Per-invocation Palette target resolution, including Tiles that have no Cel use.
local module = {}
local effective = dofile(app.params.effective_palette)
local layers = dofile(app.params.layer_select)
local digest = dofile(app.params.digest)

local function cel_use(sprite, cel)
  local _, owner = effective.resolve(sprite, cel.frameNumber)
  return {
    layer_path = layers.current_path(sprite, cel.layer),
    frame_number = cel.frameNumber,
    palette_frame_number = owner,
    is_reference = cel.layer.isReference,
  }
end

function module.resolve(sprite)
  local groups, by_id = {}, {}
  local function record(image, owner)
    local item = by_id[image.id]
    if item == nil then
      item = { image = image, owner = owner, cel_uses = {}, tile_uses = {} }
      by_id[image.id] = item
      groups[#groups + 1] = item
    end
    return item
  end
  for _, cel in ipairs(sprite.cels) do
    if not cel.layer.isTilemap then
      local item = record(cel.image, cel)
      item.cel_uses[#item.cel_uses + 1] = cel_use(sprite, cel)
    end
  end
  for tileset_index = 1, #sprite.tilesets do
    local tileset = sprite.tilesets[tileset_index]
    for tile_index = 0, #tileset - 1 do
      local tile = assert(tileset:tile(tile_index), "Missing Tile in Palette target resolution")
      local item =
        record(assert(tile.image, "Missing Tile Image in Palette target resolution"), tile)
      local uses = {}
      for _, cel in ipairs(sprite.cels) do
        if cel.layer.isTilemap and cel.layer.tileset == tileset then
          for pixel in cel.image:pixels() do
            if app.pixelColor.tileI(pixel()) == tile_index then
              uses[#uses + 1] = cel_use(sprite, cel)
              break
            end
          end
        end
      end
      item.tile_uses[#item.tile_uses + 1] = {
        tileset_index = tileset_index,
        tile_index = tile_index,
        cel_uses = uses,
      }
    end
  end
  return groups
end

function module.in_range(group, from_frame, to_frame, include_unused)
  local inside, outside = false, false
  local function visit(use)
    if use.frame_number >= from_frame and use.frame_number <= to_frame then
      inside = true
    else
      outside = true
    end
  end
  for _, use in ipairs(group.cel_uses) do
    visit(use)
  end
  for _, tile in ipairs(group.tile_uses) do
    if include_unused and #tile.cel_uses == 0 then inside = true end
    for _, use in ipairs(tile.cel_uses) do
      visit(use)
    end
  end
  return inside, outside
end

function module.facts(groups)
  local facts = {}
  for _, item in ipairs(groups) do
    local image = item.image
    facts[#facts + 1] = {
      cel_uses = item.cel_uses,
      tile_uses = item.tile_uses,
      width = image.width,
      height = image.height,
      bytes_per_pixel = image.bytesPerPixel,
      mask = image.spec.transparentColor,
      content = digest.fnv1a64(image.bytes),
    }
  end
  return facts
end

function module.tile_metadata(sprite)
  local facts = {}
  for tileset_index = 1, #sprite.tilesets do
    local tileset = sprite.tilesets[tileset_index]
    local tiles = {}
    for index = 0, #tileset - 1 do
      local tile = tileset:tile(index)
      local color = tile.color
      tiles[#tiles + 1] = {
        data = tile.data,
        color = { red = color.red, green = color.green, blue = color.blue, alpha = color.alpha },
        tile_key = tile.properties("aigengame.spa").tile_key,
      }
    end
    facts[#facts + 1] = tiles
  end
  return facts
end

return module
