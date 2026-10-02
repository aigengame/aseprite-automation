local modes = { rgb = ColorMode.RGB, grayscale = ColorMode.GRAY, indexed = ColorMode.INDEXED }
local sprite = Sprite(5, 5, modes[app.params.mode])
local palette = Palette(tonumber(app.params.palette_size) or 256)
for i = 0, #palette - 1 do
  palette:setColor(i, Color { r = i, g = 255 - i, b = (i * 37) % 256, a = i == 0 and 0 or 255 })
end
sprite:setPalette(palette)
sprite.layers[1].name = "Ink"
local image = sprite.cels[1].image
local function pixel(r, g, b, a, index)
  if app.params.mode == "indexed" then return index end
  if app.params.mode == "grayscale" then return app.pixelColor.graya(r, a) end
  return app.pixelColor.rgba(r, g, b, a)
end
for p in image:pixels() do
  p(
    pixel(
      10,
      20,
      30,
      app.params.opaque == "true" and 101 or 0,
      app.params.opaque == "true" and 1 or 0
    )
  )
end
image:drawPixel(2, 2, pixel(31, 79, 137, 143, 127))
image:drawPixel(0, 0, pixel(101, 67, 43, 255, 128))
image:drawPixel(4, 4, pixel(101, 67, 43, 255, 128))
image:drawPixel(2, 1, pixel(19, 23, 29, 255, 129))
image:drawPixel(1, 2, pixel(19, 23, 29, 255, 129))
if app.params.point_only == "true" then
  for p in image:pixels() do
    p(0)
  end
  image:drawPixel(2, 2, pixel(31, 79, 137, 255, 127))
end
if app.params.trimmed == "true" then
  local compact = Image(1, 1, ColorMode.INDEXED)
  compact:drawPixel(0, 0, 127)
  sprite.cels[1].image = compact
  sprite.cels[1].position = Point(2, 2)
end
if app.params.unsafe == "true" then image:drawPixel(4, 4, 255) end
if app.params.background == "true" then assert(app.command.BackgroundFromLayer()) end
if app.params.linked == "true" then
  sprite:newFrame(1)
  app.activeFrame = sprite.frames[1]
  app.range.frames = { 1, 2 }
  app.command.LinkCels()
end
assert(sprite:saveAs(app.params.source))
sprite:close()
