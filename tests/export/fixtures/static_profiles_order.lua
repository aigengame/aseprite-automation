-- Linear-sRGB sample isolates the selected Frame, area, and Layer before delivery.
local sprite = Sprite(5, 1, ColorMode.RGB)
sprite:assignColorSpace(ColorSpace { fromFile = assert(app.params.icc_file) })
local selected = sprite.layers[1]
selected.name = "sample"
for frame = 1, 2 do
  if frame > 1 then
    sprite:newEmptyFrame()
    sprite:newCel(selected, frame, Image(5, 1, ColorMode.RGB))
  end
  local image = selected:cel(frame).image
  image:drawPixel(0, 0, app.pixelColor.rgba(255, 0, 0, 255))
  local gray = frame == 1 and 20 or 100
  image:drawPixel(1, 0, app.pixelColor.rgba(gray, gray, gray, 255))
  image:drawPixel(2, 0, app.pixelColor.rgba(0, 0, 0, 255))
  image:drawPixel(3, 0, app.pixelColor.rgba(255, 255, 255, 255))
  image:drawPixel(4, 0, app.pixelColor.rgba(0, 0, 255, 255))
end
local excluded = sprite:newLayer()
excluded.name = "excluded"
local image = Image(5, 1, ColorMode.RGB)
image:clear(app.pixelColor.rgba(0, 255, 0, 255))
sprite:newCel(excluded, 2, image)
assert(sprite:saveAs(app.params.out))
sprite:close()
