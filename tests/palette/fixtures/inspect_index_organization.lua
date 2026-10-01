-- Independent public-API observation of Indexed ownership and known metadata.
local sprite = assert(app.open(app.params.source))
local result =
  { transparent_color_index = sprite.transparentColor, palettes = {}, cels = {}, tilesets = {} }
local ordinals, count = {}, 0
local function image_record(image)
  if not ordinals[image.id] then
    count = count + 1
    ordinals[image.id] = count
  end
  local pixels, bytes = {}, {}
  for y = 0, image.height - 1 do
    for x = 0, image.width - 1 do
      pixels[#pixels + 1] = image:getPixel(x, y)
    end
  end
  for i = 1, #image.bytes do
    bytes[i] = image.bytes:byte(i)
  end
  return {
    shared_image_ordinal = ordinals[image.id],
    pixels = pixels,
    bytes = bytes,
    width = image.width,
    height = image.height,
    color_mode = image.colorMode,
    transparent_color_index = image.spec.transparentColor,
  }
end
local function color_record(color)
  return { r = color.red, g = color.green, b = color.blue, a = color.alpha }
end
local function properties_record(properties)
  local values = {}
  for key, value in pairs(properties) do
    values[key] = value
  end
  return values
end
for palette_index = 1, #sprite.palettes do
  local palette = sprite.palettes[palette_index]
  local entries = {}
  for i = 0, #palette - 1 do
    entries[#entries + 1] = color_record(palette:getColor(i))
  end
  result.palettes[#result.palettes + 1] =
    { frame_number = palette.frame.frameNumber, entries = entries }
end
local function visit(layers, prefix)
  for _, layer in ipairs(layers) do
    local path = prefix .. layer.name
    if layer.isGroup then
      visit(layer.layers, path .. "/")
    else
      for _, cel in ipairs(layer.cels) do
        local record = image_record(cel.image)
        record.layer_path, record.frame_number = path, cel.frame.frameNumber
        record.is_reference, record.is_tilemap = layer.isReference, layer.isTilemap
        record.opacity, record.z_index = cel.opacity, cel.zIndex
        record.position = { x = cel.position.x, y = cel.position.y }
        if layer.isTilemap then
          record.tile_indexes, record.tile_flags = {}, {}
          for i, value in ipairs(record.pixels) do
            record.tile_indexes[i] = app.pixelColor.tileI(value)
            record.tile_flags[i] = value & 0xe0000000
          end
        end
        result.cels[#result.cels + 1] = record
      end
    end
  end
end
visit(sprite.layers, "")
for index = 1, #sprite.tilesets do
  local tileset = sprite.tilesets[index]
  local record = { index = index, name = tileset.name, base_index = tileset.baseIndex, tiles = {} }
  for i = 0, #tileset - 1 do
    local tile = tileset:tile(i)
    local item = image_record(tile.image)
    item.tile_index, item.data, item.color = i, tile.data, color_record(tile.color)
    item.properties = properties_record(tile.properties)
    item.spa_properties = properties_record(tile.properties("aigengame.spa"))
    item.other_properties = properties_record(tile.properties("other.plugin"))
    record.tiles[#record.tiles + 1] = item
  end
  result.tilesets[#result.tilesets + 1] = record
end
local file = assert(io.open(app.params.response, "wb"))
result.rendered = {}
for frame = 1, #sprite.frames do
  local spec = sprite.spec
  spec.colorMode, spec.transparentColor = ColorMode.RGB, 0
  local image = Image(spec)
  image:drawSprite(sprite, frame)
  local pixels = {}
  for pixel in image:pixels() do
    pixels[#pixels + 1] = pixel()
  end
  result.rendered[#result.rendered + 1] = pixels
end
file:write(json.encode(result))
file:close()
sprite:close()
