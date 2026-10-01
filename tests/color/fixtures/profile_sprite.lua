local sprite
if app.params.action == "create" then
  local mode = ColorMode.RGB
  if app.params.mode == "grayscale" then mode = ColorMode.GRAY end
  if app.params.mode == "indexed" then mode = ColorMode.INDEXED end
  sprite = Sprite(3, 1, mode)
  sprite:assignColorSpace(ColorSpace { sRGB = true })
  local palette = sprite.palettes[1]
  palette:resize(4)
  for i = 0, 3 do
    palette:setColor(i, Color { r = 32 + i * 40, g = 70 + i * 30, b = 130 - i * 20, a = 255 })
  end
  local image = sprite.cels[1].image
  for x = 0, 2 do
    local pixel = app.pixelColor.rgba(48 + x * 30, 96 + x * 30, 144 - x * 20, 255 - x * 60)
    if mode == ColorMode.GRAY then pixel = app.pixelColor.graya(48 + x * 30, 255 - x * 60) end
    if mode == ColorMode.INDEXED then pixel = x + 1 end
    image:drawPixel(x, 0, pixel)
  end
  if app.params.p3_sample == "true" then
    image:drawPixel(0, 0, app.pixelColor.rgba(180, 70, 30, 127))
  end
  if app.params.black == "true" then
    image:clear(app.pixelColor.rgba(0, 0, 0, 255))
    for i = 0, #palette - 1 do
      palette:setColor(i, Color { r = 0, g = 0, b = 0, a = 255 })
    end
  end
  if app.params.timeline == "true" then
    app.activeSprite = sprite
    app.activeLayer = sprite.layers[1]
    app.activeFrame = sprite.frames[1]
    app.command.NewFrame { content = "cellinked" }
    sprite:newEmptyFrame()
    sprite:newCel(sprite.layers[1], 3, Image(sprite.cels[1].image), Point(0, 0))
  end
  if app.params.tiles == "true" then
    sprite.gridBounds = Rectangle(0, 0, 1, 1)
    app.activeSprite = sprite
    app.activeFrame = sprite.frames[1]
    app.command.NewLayer { tilemap = true }
    app.useTool {
      tool = "pencil",
      layer = sprite.layers[2],
      color = app.pixelColor.rgba(48, 96, 144, 255),
      tilesetMode = TilesetMode.STACK,
      points = { Point(0, 0) },
    }
  end
  assert(sprite:saveAs(app.params.source))
  sprite:close()
  sprite = assert(app.open(app.params.source))
else
  sprite = assert(app.open(app.params.source))
end
if app.params.action == "convert" then
  sprite:convertColorSpace(
    app.params.icc and ColorSpace { fromFile = app.params.icc } or ColorSpace { sRGB = true }
  )
  assert(sprite:saveAs(app.params.output))
  sprite:close()
  sprite = assert(app.open(app.params.output))
end
local pixels = {}
for pixel in sprite.cels[1].image:pixels() do
  pixels[#pixels + 1] = pixel()
end
local entries = {}
for i = 0, #sprite.palettes[1] - 1 do
  entries[#entries + 1] = sprite.palettes[1]:getColor(i).rgbaPixel
end
local cels, links, tilesets, palettes = {}, {}, {}, {}
for index, cel in ipairs(sprite.cels) do
  local values = {}
  for pixel in cel.image:pixels() do
    values[#values + 1] = pixel()
  end
  cels[index] = { frame = cel.frameNumber, pixels = values, layer = cel.layer.name }
  for prior = 1, index - 1 do
    if cel.image == sprite.cels[prior].image then links[#links + 1] = { prior, index } end
  end
end
for index = 1, #sprite.tilesets do
  local tiles = {}
  for ti = 0, #sprite.tilesets[index] - 1 do
    local values = {}
    for pixel in sprite.tilesets[index]:tile(ti).image:pixels() do
      values[#values + 1] = pixel()
    end
    tiles[#tiles + 1] = values
  end
  tilesets[index] = tiles
end
for index = 1, #sprite.palettes do
  local palette = sprite.palettes[index]
  local values = {}
  for entry = 0, #palette - 1 do
    values[#values + 1] = palette:getColor(entry).rgbaPixel
  end
  palettes[index] = { frame = palette.frame.frameNumber, entries = values }
end
local facts = {
  cels = cels,
  links = links,
  tilesets = tilesets,
  palettes = palettes,
  none = sprite.colorSpace == ColorSpace(),
  srgb = sprite.colorSpace == ColorSpace { sRGB = true },
  name = sprite.colorSpace.name,
  pixels = pixels,
  entries = entries,
}
if app.params.expected_icc then
  facts.matches_requested_icc = sprite.colorSpace
    == ColorSpace { fromFile = app.params.expected_icc }
end
sprite:close()
print(json.encode(facts))
