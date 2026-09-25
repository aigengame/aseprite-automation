local mode = app.params.mode or "rgb"
local native_mode = ColorMode.RGB
if mode == "grayscale" then native_mode = ColorMode.GRAY end
if mode == "indexed" then native_mode = ColorMode.INDEXED end
local sprite = Sprite(2, 1, native_mode)
if app.params.profile == "none" then
  sprite:assignColorSpace(ColorSpace())
elseif app.params.profile == "icc" then
  sprite:assignColorSpace(ColorSpace { fromFile = assert(app.params.icc_file) })
end
if mode == "rgb" then
  local image = sprite.layers[1].cels[1].image
  if app.params.alpha == "opaque" then
    image:putPixel(0, 0, app.pixelColor.rgba(11, 22, 33, 255))
    image:putPixel(1, 0, app.pixelColor.rgba(44, 55, 66, 255))
  elseif app.params.alpha == "transparent" then
    image:putPixel(0, 0, app.pixelColor.rgba(0, 0, 0, 0))
    image:putPixel(1, 0, app.pixelColor.rgba(0, 0, 0, 0))
  else
    image:putPixel(0, 0, app.pixelColor.rgba(11, 22, 33, 127))
  end
end
if app.params.two_frames == "true" then
  local first_cel = sprite.layers[1]:cel(1)
  sprite:newEmptyFrame()
  sprite:newCel(sprite.layers[1], 2, Image(first_cel.image))
end
assert(sprite:saveAs(app.params.out))
sprite:close()
