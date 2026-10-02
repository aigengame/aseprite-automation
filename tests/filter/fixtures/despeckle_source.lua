-- All component combinations are representable in the Indexed test Palette.
local modes = { rgb = ColorMode.RGB, grayscale = ColorMode.GRAY, indexed = ColorMode.INDEXED }
local duplicate = app.params.duplicate == "true"
local mode = app.params.mode
local sprite = Sprite(duplicate and 1 or 3, app.params.grid == "true" and 3 or 1, modes[mode])
local colors = { 40, 100, 200 }
local alphas = { 60, 128, 255 }
local palette = Palette(82)
palette:setColor(0, Color { r = 0, g = 0, b = 0, a = 0 })
local lookup = {}
local index = 1
for _, r in ipairs(colors) do
  for _, g in ipairs(colors) do
    for _, b in ipairs(colors) do
      for _, a in ipairs(alphas) do
        palette:setColor(index, Color { r = r, g = g, b = b, a = a })
        lookup[app.pixelColor.rgba(r, g, b, a)] = index
        index = index + 1
      end
    end
  end
end
if duplicate then
  palette = Palette(4)
  palette:setColor(0, Color { r = 0, g = 0, b = 0, a = 0 })
  palette:setColor(1, Color { r = 80, g = 120, b = 160, a = 255 })
  palette:setColor(2, palette:getColor(1))
  palette:setColor(3, Color { r = 255, g = 255, b = 255, a = 255 })
end
sprite:setPalette(palette)
local values = { { 100, 200, 40, 128 }, { 200, 40, 100, 60 }, { 40, 100, 200, 255 } }
local image = sprite.cels[1].image
for y = 0, sprite.height - 1 do
  for x = 0, sprite.width - 1 do
    local v = values[(x + y) % 3 + 1]
    local rgba = app.pixelColor.rgba(v[1], v[2], v[3], v[4])
    image:drawPixel(
      x,
      y,
      duplicate and tonumber(app.params.index or "1")
        or (
          mode == "indexed" and lookup[rgba]
          or (mode == "rgb" and rgba or app.pixelColor.graya(v[1], v[4]))
        )
    )
  end
end
if app.params.background == "true" then assert(app.command.BackgroundFromLayer()) end
if app.params.linked == "true" then assert(app.command.NewFrame { content = "cellinked" }) end
assert(sprite:saveAs(app.params.source))
sprite:close()
