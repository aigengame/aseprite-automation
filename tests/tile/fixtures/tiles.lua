local modes = { rgb = ColorMode.RGB, grayscale = ColorMode.GRAY, indexed = ColorMode.INDEXED }
local mode = modes[app.params.mode or "rgb"]
local s = Sprite(16, 16, mode)
s.gridBounds = Rectangle(0, 0, 2, 3)
app.activeSprite = s
app.command.NewLayer { tilemap = true, ui = false }
local first = app.activeLayer
first.name = "map"
local ts = first.tileset
ts.name = "terrain"
ts.baseIndex = tonumber(app.params.base_index or "1")
for index = 1, 4 do
  local tile = s:newTile(ts)
  tile.image:clear(mode == ColorMode.RGB and app.pixelColor.rgba(index * 40, 30, 20, 255) or index)
  if index ~= 3 then
    tile.properties("aigengame.spa").tile_key = index == 4 and "red" or ({ "red", "green" })[index]
  end
end
local mw, mh = tonumber(app.params.map_width or "3"), tonumber(app.params.map_height or "2")
local m = Image(mw, mh, ColorMode.TILEMAP)
m:clear(0)
m:putPixel(0, 0, 1)
m:putPixel(2, 0, 2 | 0x80000000)
m:putPixel(0, 1, 3 | 0x60000000)
m:putPixel(2, 1, 4 | 0xe0000000)
if mw > 3 then m:putPixel(mw - 1, mh - 1, 2) end
if app.params.invalid_index == "true" then m:putPixel(1, 0, 99 | 0x80000000) end
if app.params.flagged_zero == "true" then
  ts:tile(0).image:clear(app.pixelColor.rgba(255, 0, 0, 255))
  m:putPixel(1, 0, 0xe0000000)
end
s:newCel(first, 1, m, Point(-5, 7))
s:newEmptyFrame()
app.activeLayer = first
app.command.NewLayer { tilemap = true, ui = false }
local shared = app.activeLayer
shared.name = "shared"
shared.tileset = ts
s:newCel(shared, 2, Image(m), Point(3, -2))
local extra = s:newTileset(Grid { x = 0, y = 0, width = 4, height = 4 })
extra.name = app.params.duplicate_name == "true" and "terrain" or "orphan"
assert(s:saveAs(app.params.source))
s:close()
