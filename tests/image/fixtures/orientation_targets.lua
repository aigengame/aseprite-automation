local mode = app.params.mode or "rgb"
local kind = app.params.kind or "regular"
local color_mode = mode == "indexed" and ColorMode.INDEXED
  or mode == "grayscale" and ColorMode.GRAY
  or ColorMode.RGB
local sprite = Sprite(12, 10, color_mode)
local layer = sprite.layers[1]
layer.name = "subject"
local image = Image(3, 2, color_mode)
local alpha = { 255, 128, 0, 255, 64, 255 }
if mode == "indexed" then
  local palette = Palette(7)
  for index = 0, 6 do
    palette:setColor(index, Color { r = index * 20, g = 17, b = 33, a = 255 })
  end
  sprite:setPalette(palette)
  sprite.transparentColor = 3
end
for index = 1, 6 do
  local value = mode == "indexed" and index
    or mode == "grayscale" and app.pixelColor.graya(index + 10, alpha[index])
    or app.pixelColor.rgba(index + 10, index + 20, index + 30, alpha[index])
  image:putPixel((index - 1) % 3, (index - 1) // 3, value)
end
sprite:newCel(layer, 1, image, Point(4, 5))
app.activeSprite = sprite
app.activeLayer = layer
app.activeFrame = sprite.frames[1]
if kind == "background" then
  app.command.BackgroundFromLayer()
elseif kind == "reference" then
  app.command.NewLayer { reference = true, ui = false }
  layer = app.activeLayer
  assert(layer.isReference)
  layer.name = "subject-reference"
  sprite:newCel(layer, 1, image, Point(4, 5))
elseif kind == "tilemap" then
  app.command.NewLayer { tilemap = true, ui = false }
  layer = app.activeLayer
  assert(layer.isTilemap)
elseif kind == "group" then
  sprite:newGroup()
elseif kind == "absent" then
  sprite:deleteCel(layer, 1)
else
  app.command.NewFrame { content = "cellinked" }
  assert(layer:cel(1).image == layer:cel(2).image)
  layer:cel(1).opacity = 200
  layer:cel(2).zIndex = 1
  sprite:newEmptyFrame(3)
  sprite:newCel(layer, 3, Image(image), Point(-2, -1))
  local tag = sprite:newTag(1, 3)
  tag.name = "unchanged"
  sprite.gridBounds = Rectangle(1, 2, 3, 4)
end
assert(sprite:saveAs(app.params.out))
sprite:close()
