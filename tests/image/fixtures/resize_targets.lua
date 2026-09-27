local mode = app.params.mode or "rgb"
local indexed = mode:sub(1, 7) == "indexed"
local color_mode = indexed and ColorMode.INDEXED
  or mode:sub(1, 9) == "grayscale" and ColorMode.GRAY
  or ColorMode.RGB
local sprite = Sprite(8, 8, color_mode)
local layer = sprite.layers[1]
layer.name = "subject"
local image = Image(2, 2, color_mode)
if indexed then
  local offset_mask = mode:find("indexed-offset-mask", 1, true) == 1
  local zero_after = mode == "indexed-offset-mask-zero-after"
  local duplicate = mode == "indexed-offset-mask-duplicate"
  local palette =
    Palette(mode == "indexed-offset-mask-large-palette" and 257 or offset_mask and 5 or 4)
  palette:setColor(
    0,
    Color {
      r = 0,
      g = 0,
      b = 0,
      a = offset_mask and mode ~= "indexed-offset-mask-zero-before" and 255 or 0,
    }
  )
  palette:setColor(1, Color { r = 255, g = 0, b = 0, a = 255 })
  palette:setColor(2, Color { r = 0, g = 0, b = 255, a = 255 })
  local third_color = (zero_after or duplicate) and 0 or 127
  palette:setColor(
    3,
    Color {
      r = third_color,
      g = 0,
      b = third_color,
      a = zero_after and 0 or 255,
    }
  )
  if offset_mask then
    palette:setColor(
      4,
      Color {
        r = duplicate and 255 or zero_after and 127 or 25,
        g = 0,
        b = zero_after and 127 or 0,
        a = 255,
      }
    )
  end
  sprite:setPalette(palette)
  if offset_mask then sprite.transparentColor = 2 end
  local left_index = mode == "indexed-offset-mask-black" and 0 or 1
  image:putPixel(0, 0, left_index)
  if mode ~= "indexed-edge" then
    image:putPixel(1, 0, 2)
    image:putPixel(0, 1, left_index)
    image:putPixel(1, 1, 2)
  end
elseif mode:sub(1, 9) == "grayscale" then
  image:putPixel(0, 0, app.pixelColor.graya(200, 255))
else
  image:putPixel(0, 0, app.pixelColor.rgba(255, 0, 0, 255))
  if mode ~= "rgb-edge" then image:putPixel(1, 0, app.pixelColor.rgba(0, 0, 255, 255)) end
end
if mode == "rgb-hidden" then
  image:putPixel(1, 1, app.pixelColor.rgba(17, 29, 41, 0))
elseif mode == "grayscale-hidden" then
  image:putPixel(1, 1, app.pixelColor.graya(73, 0))
end
sprite:newCel(layer, 1, image, Point(mode == "position-limit" and 32767 or 1, 2))
if mode == "linked" or mode == "indexed-linked" then
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
