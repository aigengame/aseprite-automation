local modes = { rgb = ColorMode.RGB, grayscale = ColorMode.GRAY, indexed = ColorMode.INDEXED }
local mode = app.params.mode or "rgb"
local sprite = Sprite(3, 1, modes[mode])
if app.params.profile == "none" then sprite:assignColorSpace(ColorSpace()) end
if app.params.icc_file then
  sprite:assignColorSpace(ColorSpace { fromFile = app.params.icc_file })
end
local palette = Palette(8)
for i = 0, 7 do
  palette:setColor(i, Color { r = i * 20, g = 30, b = 40, a = 255 })
end
palette:setColor(1, Color { r = 200, g = 10, b = 20, a = 128 })
palette:setColor(2, palette:getColor(1)) -- Preserve duplicate and unused entries.
sprite:setPalette(palette)
sprite.transparentColor = 7
app.activeSprite = sprite
if app.params.background == "true" then app.command.BackgroundFromLayer { ui = false } end
local image = Image(sprite.spec)
if mode == "indexed" then
  image.bytes = string.char(7, 1, 2)
elseif mode == "grayscale" then
  image.bytes = string.char(0, 0, 80, 128, 200, 255)
else
  image.bytes = string.char(0, 0, 0, 0, 200, 10, 20, 128, 20, 30, 40, 255)
end
sprite.cels[1].image = image
app.command.NewFrame { content = "cellinked" }
assert(sprite:saveAs(app.params.out))
sprite:close()
