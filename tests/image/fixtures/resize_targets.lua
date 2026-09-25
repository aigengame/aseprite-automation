local mode = app.params.mode or "rgb"
local color_mode = (mode == "indexed" or mode == "indexed-two-frame") and ColorMode.INDEXED
  or mode == "grayscale" and ColorMode.GRAY
  or ColorMode.RGB
local sprite = Sprite(8, 8, color_mode)
local layer = sprite.layers[1]
layer.name = "subject"
local image = Image(2, 2, color_mode)
if mode == "indexed" or mode == "indexed-two-frame" then
  local palette = Palette(4)
  palette:setColor(0, Color { r = 0, g = 0, b = 0, a = 0 })
  palette:setColor(1, Color { r = 255, g = 0, b = 0, a = 255 })
  palette:setColor(2, Color { r = 0, g = 0, b = 255, a = 255 })
  palette:setColor(3, Color { r = 127, g = 0, b = 127, a = 255 })
  sprite:setPalette(palette)
  image:putPixel(0, 0, 1)
  image:putPixel(1, 0, 2)
  image:putPixel(0, 1, 1)
  image:putPixel(1, 1, 2)
elseif mode == "grayscale" then
  image:putPixel(0, 0, app.pixelColor.graya(200, 255))
else
  image:putPixel(0, 0, app.pixelColor.rgba(255, 0, 0, 255))
  if mode ~= "rgb-edge" then image:putPixel(1, 0, app.pixelColor.rgba(0, 0, 255, 255)) end
end
sprite:newCel(layer, 1, image, Point(1, 2))
if app.params.mode == "linked" then
  sprite:newEmptyFrame(2)
  app.activeSprite = sprite
  app.activeLayer = layer
  app.activeFrame = sprite.frames[1]
  app.command.NewFrame { content = "cellinked" }
  local linked = assert(layer:cel(2))
  assert(linked.image == layer:cel(1).image)
elseif mode == "absent" then
  sprite:newEmptyFrame(2)
elseif mode == "indexed-two-frame" then
  sprite:newEmptyFrame(2)
elseif mode == "background" then
  app.activeSprite = sprite
  app.activeLayer = layer
  app.activeFrame = sprite.frames[1]
  app.command.BackgroundFromLayer()
elseif mode == "reference" then
  app.activeSprite = sprite
  app.activeLayer = layer
  app.activeFrame = sprite.frames[1]
  app.command.NewLayer { reference = true }
elseif mode == "tilemap" then
  app.activeSprite = sprite
  app.activeLayer = layer
  app.activeFrame = sprite.frames[1]
  app.command.NewLayer { tilemap = true }
end
assert(sprite:saveAs(app.params.out))
sprite:close()
