local sprite = Sprite(2, 1, ColorMode.RGB)
local alpha = app.params.background == "true" and 255 or 100
local palette = Palette(2)
palette:setColor(0, Color { r = 0, g = 0, b = 0, a = 0 })
palette:setColor(1, Color { r = 80, g = 40, b = 20, a = alpha })
sprite:setPalette(palette)
sprite.cels[1].image:drawPixel(0, 0, app.pixelColor.rgba(80, 40, 20, alpha))
sprite.cels[1].image:drawPixel(1, 0, app.pixelColor.rgba(80, 40, 20, alpha == 255 and 255 or 101))
if app.params.background == "true" then assert(app.command.BackgroundFromLayer()) end
sprite:saveAs(app.params.source)
sprite:close()
