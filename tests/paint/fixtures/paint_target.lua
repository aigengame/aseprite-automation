-- Native fixtures for Paint target semantics that Sprite create does not yet expose.
local kind = assert(app.params.kind)
local target = assert(app.params.out)
local sprite

if kind == "linked-rgb" then
  sprite = Sprite(4, 3, ColorMode.RGB)
  local layer = sprite.layers[1]
  local image = Image(2, 2, ColorMode.RGB)
  image:clear(app.pixelColor.rgba(0, 0, 0, 0))
  local first = assert(layer:cel(1))
  first.image = image
  first.position = Point(1, 0)
  layer.isContinuous = true
  sprite:newFrame(1)
  layer.isContinuous = false
  local third_frame = sprite:newEmptyFrame()
  sprite:newCel(layer, third_frame, Image(first.image), Point(1, 0))
elseif kind == "grayscale" then
  sprite = Sprite(2, 2, ColorMode.GRAY)
elseif kind == "indexed" then
  sprite = Sprite(2, 2, ColorMode.INDEXED)
  local palette = Palette(2)
  palette:setColor(0, Color{ r=0, g=0, b=0, a=0 })
  palette:setColor(1, Color{ r=241, g=82, b=65, a=255 })
  sprite:setPalette(palette)
elseif kind == "group" then
  sprite = Sprite(2, 2, ColorMode.RGB)
  local image_layer = sprite.layers[1]
  sprite:newGroup()
  sprite:deleteLayer(image_layer)
else
  error("unknown Paint fixture kind")
end

assert(sprite:saveAs(target), "could not save Paint fixture")
sprite:close()
