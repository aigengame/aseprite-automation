local modes = { rgb = ColorMode.RGB, grayscale = ColorMode.GRAY, indexed = ColorMode.INDEXED }
local sprite = Sprite(3, 1, modes[app.params.mode])
local palette = Palette(8)
local colors = {
  { 0, 0, 0, 0 },
  { 100, 60, 20, 128 },
  { 134, 72, 10, 128 },
  { 120, 60, 0, 128 },
  { 218, 111, 4, 128 },
  { 151, 76, 0, 128 },
  { 100, 60, 20, 192 },
  { 80, 40, 20, 255 },
}
for i, c in ipairs(colors) do
  palette:setColor(i - 1, Color { r = c[1], g = c[2], b = c[3], a = c[4] })
end
sprite:setPalette(palette)
sprite.layers[1].name = "Ink"
local image = sprite.cels[1].image
for x = 0, 2 do
  image:drawPixel(
    x,
    0,
    app.params.mode == "indexed" and 1
      or (
        app.params.mode == "grayscale" and app.pixelColor.graya(80, 128)
        or app.pixelColor.rgba(100, 60, 20, 128)
      )
  )
end
if app.params.transparent == "true" then image:drawPixel(0, 0, 0) end
if app.params.background == "true" then assert(app.command.BackgroundFromLayer()) end
assert(sprite:saveAs(app.params.source))
sprite:close()
