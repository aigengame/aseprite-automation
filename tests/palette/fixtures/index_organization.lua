-- Indexed ownership fixture. Additional Palette Changes are injected by Python.
local sprite = Sprite(3, 1, ColorMode.INDEXED)
local palette = sprite.palettes[1]
palette:resize(4)
for i, color in ipairs({
  Color { r = 10, g = 20, b = 30, a = 255 },
  Color { r = 240, g = 40, b = 60, a = 255 },
  Color { r = 20, g = 200, b = 40, a = 128 },
  Color { r = 50, g = 60, b = 70, a = 0 },
}) do
  palette:setColor(i - 1, color)
end
sprite.transparentColor = 3
local ordinary = sprite.layers[1]
ordinary.name = "Ordinary"
ordinary:cel(1).image.bytes = string.char(1, 3, 2)
app.activeSprite, app.activeLayer = sprite, ordinary
app.command.NewFrame { content = "cellinked" }
local cross_link = app.params.cross_link == "true"
for frame = 3, 4 do
  if cross_link then
    app.activeFrame = sprite.frames[frame - 1]
    app.command.NewFrame { content = "cellinked" }
  else
    sprite:newEmptyFrame()
    sprite:newCel(ordinary, frame, Image(ordinary:cel(1).image), Point(0, 0))
  end
end
app.activeFrame = sprite.frames[1]
app.command.NewLayer { reference = true, ui = false }
local reference = app.activeLayer
reference.name = "Reference"
for frame = 1, 4 do
  local image = Image(3, 1, ColorMode.INDEXED)
  image.bytes = string.char(2, 3, 1)
  sprite:newCel(reference, frame, image, Point(0, 0))
end
sprite.gridBounds = Rectangle(0, 0, 1, 1)
app.activeLayer = ordinary
app.command.NewLayer { tilemap = true, ui = false }
local tilemap = app.activeLayer
tilemap.name = "Tilemap"
local tileset = tilemap.tileset
tileset.name = "Palette Tiles"
for i = 1, 3 do
  local tile = sprite:newTile(tileset)
  tile.image.bytes = string.char(i)
  tile.data = "tile-data-" .. i
  tile.color = Color { r = 20 * i, g = 30, b = 40, a = 255 }
  tile.properties.default_note = "default-" .. i
  tile.properties("aigengame.spa").tile_key = "tile-key-" .. i
  tile.properties("other.plugin").note = "other-" .. i
end
for frame = 1, 4 do
  local image = Image(3, 1, ColorMode.TILEMAP)
  local first = (app.params.mode == "cross-range" or frame <= 2) and 1 or 2
  image:drawPixel(0, 0, first | 0x80000000)
  image:drawPixel(1, 0, 2 | 0x40000000)
  image:drawPixel(2, 0, 0)
  sprite:newCel(tilemap, frame, image, Point(0, 0))
end
sprite.transparentColor = 3
assert(ordinary:cel(1).image.id == ordinary:cel(2).image.id)
assert(#tileset == 4)
if
  app.params.mode == "unused-only"
  or app.params.mode == "reference-only"
  or app.params.mode == "linked-only"
then
  for _, cel in ipairs(sprite.cels) do
    if not cel.layer.isTilemap then cel.image.bytes = string.char(1, 1, 1) end
  end
  for index = 1, 3 do
    tileset:tile(index).image:putPixel(0, 0, 1)
  end
  sprite.transparentColor = 0
  if app.params.mode == "unused-only" then
    tileset:tile(3).image:putPixel(0, 0, 2)
  elseif app.params.mode == "reference-only" then
    reference:cel(1).image:putPixel(0, 0, 2)
  else
    for _, cel in ipairs(reference.cels) do
      cel.image:clear(0)
    end
  end
end
assert(sprite:saveAs(app.params.source))
sprite:close()
