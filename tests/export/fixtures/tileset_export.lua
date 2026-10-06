-- Shared native source for the Tileset atlas, Palette, and Profile export matrix.
local modes = { rgb = ColorMode.RGB, grayscale = ColorMode.GRAY, indexed = ColorMode.INDEXED }
local mode = modes[app.params.mode or "rgb"]
local large = app.params.large_colors == "true"
assert(not large or mode == ColorMode.RGB, "Large color fixture requires RGB")
local width, height = large and 257 or 2, large and 1 or 2
local sprite = Sprite(width * 3, height * 2, mode)
if mode == ColorMode.INDEXED then
  sprite.transparentColor = tonumber(app.params.transparent or "7")
end
sprite.gridBounds = Rectangle(0, 0, width, height)
app.activeSprite = sprite
app.command.NewLayer { tilemap = true, ui = false }
local layer = app.activeLayer
layer.name = "map"
local tileset = layer.tileset
tileset.name, tileset.baseIndex = "terrain", 9
for index = 1, 2 do
  local tile = sprite:newTile(tileset)
  tile.properties("aigengame.spa").tile_key = index == 1 and "used" or "unused"
  for y = 0, height - 1 do
    for x = 0, width - 1 do
      local offset, pixel = y * width + x
      if mode == ColorMode.INDEXED then
        pixel = index == 1 and ({ 0, 1, 2, 7 })[offset + 1] or 4
      elseif mode == ColorMode.GRAY then
        pixel = app.pixelColor.graya(30 + offset * 40, ({ 255, 128, 1, 255 })[offset + 1])
      elseif large then
        pixel = app.pixelColor.rgba(x % 256, x // 256, index * 20, 255)
      else
        pixel =
          app.pixelColor.rgba(30 + offset * 40, index * 20, 60, ({ 255, 128, 1, 255 })[offset + 1])
      end
      tile.image:putPixel(x, y, pixel)
    end
  end
end
if app.params.bad_key == "missing" then
  tileset:tile(2).properties("aigengame.spa").tile_key = nil
elseif app.params.bad_key == "duplicate" then
  tileset:tile(2).properties("aigengame.spa").tile_key = "used"
elseif app.params.bad_key == "invalid" then
  tileset:tile(2).properties("aigengame.spa").tile_key = ""
end
local map = Image(3, 2, ColorMode.TILEMAP)
map:clear(0)
map:putPixel(0, 0, 1)
map:putPixel(2, 0, 1 | app.pixelColor.TILE_XFLIP)
map:putPixel(1, 1, 1 | app.pixelColor.TILE_YFLIP | app.pixelColor.TILE_DFLIP)
if app.params.invalid_index == "true" then map:putPixel(1, 0, 99) end
if app.params.flagged_zero == "true" then map:putPixel(1, 0, app.pixelColor.TILE_XFLIP) end
sprite:newCel(layer, 1, map, Point(-5, 7))
sprite:newEmptyFrame()
sprite:newCel(layer, 2, Image(map), Point(-5, 7))
if mode == ColorMode.INDEXED then
  local size = tonumber(app.params.palette_size or "8")
  local first = Palette(size)
  local values = {
    Color { r = 11, g = 22, b = 33, a = 255 },
    Color { r = 255, g = 0, b = 0, a = 255 },
    Color { r = 80, g = 90, b = 100, a = 128 },
    Color { r = 80, g = 90, b = 100, a = 128 },
    Color { r = 50, g = 60, b = 70, a = 1 },
    Color { r = 90, g = 10, b = 40, a = 0 },
    Color { r = 255, g = 255, b = 255, a = 255 },
    Color { r = 4, g = 5, b = 6, a = 255 },
  }
  for index = 0, size - 1 do
    first:setColor(index, values[index + 1] or Color { r = 1, g = 2, b = 3, a = 255 })
  end
  app.activeFrame = sprite.frames[1]
  sprite:setPalette(first)
  -- E2E injects the Frame 2 Palette Chunk through tests.support.inject_palette_change;
  -- the public Sprite:setPalette API always updates Frame 1.
end
local profile = app.params.profile or "none"
if profile == "none" then
  sprite:assignColorSpace(ColorSpace())
elseif profile == "srgb" then
  sprite:assignColorSpace(ColorSpace { sRGB = true })
else
  sprite:assignColorSpace(ColorSpace { fromFile = assert(app.params.icc_file) })
end
assert(sprite:saveAs(app.params.source or app.params.out))
sprite:close()
