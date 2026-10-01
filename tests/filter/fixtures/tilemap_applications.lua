-- Independent native fixture, command oracle, and reopened pixel observation.
local mode = app.params.mode
local modes = { rgb = ColorMode.RGB, grayscale = ColorMode.GRAY, indexed = ColorMode.INDEXED }
local function color(r, a) return Color { r = r, g = 40, b = 20, a = a } end
local sprite
if app.params.action == "create" then
  sprite = Sprite(3, 1, modes[mode])
  local first = Palette(5)
  first:setColor(0, color(0, 0))
  first:setColor(1, color(20, 100))
  first:setColor(2, color(30, 101))
  first:setColor(3, color(40, 200))
  first:setColor(4, color(40, 200))
  sprite:setPalette(first)
  sprite:newEmptyFrame()
  app.activeFrame = sprite.frames[2]
  sprite.gridBounds = Rectangle(0, 0, 3, 1)
  app.command.NewLayer { tilemap = true, ui = false }
  local layer = app.activeLayer
  layer.name = "Tiles"
  local tile = sprite:newTile(layer.tileset)
  for x = 0, 2 do
    local value
    if mode == "indexed" then
      value = x == 0 and 1 or (x == 1 and 0 or 4)
    elseif mode == "grayscale" then
      value = app.pixelColor.graya(80 + x * 20, 100 + x)
    else
      value = app.pixelColor.rgba(80, 40, 20, x == 2 and 101 or 100)
    end
    tile.image:putPixel(x, 0, value)
  end
  local map = Image(1, 1, ColorMode.TILEMAP)
  map:putPixel(0, 0, 1)
  sprite:newCel(layer, 1, map, Point(0, 0))
  sprite:newCel(layer, 2, Image(map), Point(0, 0))
  sprite:deleteLayer(sprite.layers[1])
  assert(sprite:saveAs(app.params.source))
else
  sprite = assert(app.open(app.params.source))
end
if app.params.action == "native" then
  local layer = sprite.layers[1]
  app.activeCel = layer:cel(tonumber(app.params.basis or "2"))
  assert(app.site.tilesetMode == TilesetMode.MANUAL)
  app.range:clear()
  app.range.layers = { layer }
  app.range.frames = { 1 }
  app.range.colors = app.params.palette == "true" and { 1 } or {}
  sprite.selection = Selection(Rectangle(0, 0, 3, 1))
  local channels = mode == "grayscale" and FilterChannels.GRAY or FilterChannels.RED
  if app.params.channels then
    channels = 0
    for name in app.params.channels:gmatch("[^,]+") do
      channels = channels | FilterChannels[name:upper()]
    end
  end
  assert(app.command.BrightnessContrast {
    ui = false,
    channels = channels,
    brightness = tonumber(app.params.brightness),
    contrast = 0,
  })
  assert(sprite:saveAs(app.params.target))
end
if app.params.action == "observe" then
  local function pixels(image)
    local values = {}
    for pixel in image:pixels() do
      values[#values + 1] = pixel()
    end
    return values
  end
  local result = { maps = {}, tiles = {}, palettes = {}, resolved = {} }
  for _, cel in ipairs(sprite.cels) do
    result.maps[#result.maps + 1] = { frame = cel.frameNumber, pixels = pixels(cel.image) }
  end
  for i = 0, #sprite.tilesets[1] - 1 do
    result.tiles[#result.tiles + 1] = pixels(sprite.tilesets[1]:tile(i).image)
  end
  for number = 1, #sprite.palettes do
    local palette = sprite.palettes[number]
    local entries = {}
    for i = 0, #palette - 1 do
      local c = palette:getColor(i)
      entries[#entries + 1] = { c.red, c.green, c.blue, c.alpha }
    end
    result.palettes[#result.palettes + 1] = { frame = palette.frame.frameNumber, entries = entries }
  end
  local basis = sprite.palettes[#sprite.palettes]
  for _, value in ipairs(result.tiles[2]) do
    if mode == "indexed" then
      local c = basis:getColor(value)
      result.resolved[#result.resolved + 1] = { c.red, c.green, c.blue, c.alpha }
    elseif mode == "grayscale" then
      result.resolved[#result.resolved + 1] =
        { app.pixelColor.grayaV(value), app.pixelColor.grayaA(value) }
    else
      result.resolved[#result.resolved + 1] = {
        app.pixelColor.rgbaR(value),
        app.pixelColor.rgbaG(value),
        app.pixelColor.rgbaB(value),
        app.pixelColor.rgbaA(value),
      }
    end
  end
  local file = assert(io.open(app.params.response, "wb"))
  file:write(json.encode(result))
  file:close()
end
sprite:close()
