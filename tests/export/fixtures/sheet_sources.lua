-- Public-operation test sources. Palette changes are injected using tests.support.inject_palette_change.
app.preferences.experimental.compose_groups = true
local function save(sprite, name)
  if name == app.params.variant then assert(sprite:saveAs(app.params.out)) end
  sprite:close()
end
local duplicates = Sprite(8, 6, ColorMode.RGB)
local layer = duplicates.layers[1]
duplicates:deleteCel(layer, 1)
local red = Image(2, 1, ColorMode.RGB)
red:clear(app.pixelColor.rgba(201, 17, 29, 255))
for frame = 1, 5 do
  if frame > 1 then duplicates:newEmptyFrame() end
  if frame <= 3 then
    duplicates:newCel(layer, frame, red, frame == 3 and Point(5, 3) or Point(2, 1))
  end
  duplicates.frames[frame].duration = ({ 0.07, 0.11, 0.23, 0.04, 0.05 })[frame]
end
local tag = duplicates:newTag(1, 5)
tag.name, tag.aniDir, tag.repeats = "action", AniDir.REVERSE, 2
local nested = duplicates:newTag(2, 3)
nested.name, nested.aniDir, nested.repeats = "nested", AniDir.PING_PONG_REVERSE, 0
local singleton = duplicates:newTag(3, 3)
singleton.name, singleton.color = "one", Color { r = 10, g = 20, b = 30, a = 255 }
save(duplicates, "duplicates")

local blank = Sprite(3, 2, ColorMode.RGB)
blank:newEmptyFrame()
blank:newEmptyFrame()
save(blank, "blank")

for _, mask in ipairs({ 0, 7 }) do
  local source = Sprite(3, 1, ColorMode.INDEXED)
  local palette = Palette(8)
  for index = 0, 7 do
    palette:setColor(index, Color { r = index * 10, g = index * 11, b = index * 12, a = 255 })
  end
  palette:setColor(1, Color { r = 201, g = 17, b = 29, a = 255 })
  palette:setColor(2, Color { r = 31, g = 100, b = 151, a = 128 })
  palette:setColor(3, palette:getColor(1))
  source:setPalette(palette)
  source.transparentColor = mask
  local leaf = source.layers[1]
  leaf.name = "selected"
  leaf:cel(1).image.bytes = string.char(1, 2, mask)
  app.activeSprite, app.activeLayer, app.activeFrame = source, leaf, source.frames[1]
  app.command.NewFrame { content = "cellinked" }
  assert(leaf:cel(1).image == leaf:cel(2).image)
  source:newEmptyFrame()
  source.frames[1].duration, source.frames[2].duration, source.frames[3].duration = 0.07, 0.23, 0.04
  save(source, "indexed" .. mask .. "_linked")
end

for _, kind in ipairs({ "rgb", "indexed_mask", "indexed_other" }) do
  local indexed = kind ~= "rgb"
  local source = Sprite(8, 6, indexed and ColorMode.INDEXED or ColorMode.RGB)
  local white = indexed and (kind == "indexed_mask" and 7 or 1)
    or app.pixelColor.rgba(255, 255, 255, 255)
  if indexed then
    local palette = Palette(8)
    for index = 0, 7 do
      palette:setColor(index, Color { r = 20 * index, g = 15 * index, b = 10 * index, a = 255 })
    end
    palette:setColor(white, Color { r = 255, g = 255, b = 255, a = 255 })
    palette:setColor(2, Color { r = 255, g = 0, b = 0, a = 255 })
    palette:setColor(3, Color { r = 0, g = 255, b = 0, a = 255 })
    source:setPalette(palette)
    source.transparentColor = 7
  end
  local leaf = source.layers[1]
  for frame = 1, 2 do
    if frame > 1 then
      source:newEmptyFrame()
      source:newCel(leaf, frame, Image(8, 6, source.colorMode))
    end
    local image = leaf:cel(frame).image
    image:clear(white)
    image:drawPixel(
      frame == 1 and 2 or 6,
      frame == 1 and 1 or 4,
      indexed and (frame == 1 and 2 or 3)
        or app.pixelColor.rgba(frame == 1 and 255 or 0, frame == 1 and 0 or 255, 0, 255)
    )
    source.frames[frame].duration = frame == 1 and 0.07 or 0.11
  end
  app.activeSprite, app.activeLayer, app.activeFrame = source, leaf, source.frames[1]
  app.bgColor = indexed and Color { index = white } or Color { r = 255, g = 255, b = 255, a = 255 }
  app.command.BackgroundFromLayer()
  local selected = source:newTag(1, 1)
  selected.name = "first"
  save(source, "background_" .. kind)
end

local grouped = Sprite(3, 1, ColorMode.RGB)
local outside = grouped.layers[1]
outside.name = "outside"
outside:cel(1).image:drawPixel(2, 0, app.pixelColor.rgba(17, 181, 43, 255))
local group = grouped:newGroup()
group.name, group.opacity = "selected", 128
local inner = grouped:newGroup()
inner.parent = group
local leaf = grouped:newLayer()
leaf.parent = inner
local image = Image(1, 1, ColorMode.RGB)
image:drawPixel(0, 0, app.pixelColor.rgba(201, 17, 29, 255))
grouped:newCel(leaf, 1, image, Point(0, 0))
group.isVisible, inner.isVisible, leaf.isVisible = false, false, false
save(grouped, "hidden_group")

local reference = Sprite(2, 1, ColorMode.RGB)
reference.layers[1]:cel(1).image:drawPixel(0, 0, app.pixelColor.rgba(200, 0, 0, 255))
app.activeSprite = reference
app.command.NewLayer { reference = true, ui = false }
local ref = app.activeLayer
ref.name = "reference"
local blue = Image(1, 1, ColorMode.RGB)
blue:drawPixel(0, 0, app.pixelColor.rgba(0, 0, 200, 255))
reference:newCel(ref, 1, blue, Point(1, 0))
assert(ref.isReference)
save(reference, "reference")

if app.params.variant == "tilemap" then
  local tile_source = Sprite(3, 1, ColorMode.INDEXED)
  local palette = Palette(8)
  palette:setColor(1, Color { r = 11, g = 22, b = 33, a = 255 })
  tile_source:setPalette(palette)
  tile_source.transparentColor = 7
  tile_source.gridBounds = Rectangle(0, 0, 1, 1)
  app.activeSprite = tile_source
  app.command.NewLayer { tilemap = true, ui = false }
  app.activeLayer.name = "tiles"
  app.useTool {
    tool = "pencil",
    layer = app.activeLayer,
    color = Color { index = 1 },
    tilesetMode = TilesetMode.STACK,
    points = { Point(0, 0) },
  }
  save(tile_source, "tilemap")
end
