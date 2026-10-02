local mode = app.params.mode
local modes = { rgb = ColorMode.RGB, grayscale = ColorMode.GRAY, indexed = ColorMode.INDEXED }
local sprite = Sprite(1, 1, modes[mode])
local palette = Palette(3)
palette:setColor(0, Color { r = 0, g = 0, b = 0, a = 0 })
palette:setColor(1, Color { r = 80, g = 40, b = 20, a = 100 })
palette:setColor(2, palette:getColor(1))
sprite:setPalette(palette)
sprite.cels[1].image:drawPixel(
  0,
  0,
  mode == "indexed" and 2
    or (
      mode == "grayscale" and app.pixelColor.graya(80, 100)
      or app.pixelColor.rgba(80, 40, 20, 100)
    )
)
sprite:saveAs(app.params.source)
sprite:close()
