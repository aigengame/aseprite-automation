-- Shared, linked, and orphan Tile records with opaque native metadata.
local modes = { rgb = ColorMode.RGB, grayscale = ColorMode.GRAY, indexed = ColorMode.INDEXED }
local mode = modes[app.params.mode or "rgb"]
local sprite = Sprite(16, 16, mode)
if app.params.uuids then sprite.useLayerUuids = app.params.uuids == "true" end
sprite.transparentColor = mode == ColorMode.INDEXED and 7 or 0
if app.params.palette_size then sprite:setPalette(Palette(tonumber(app.params.palette_size))) end
app.activeSprite = sprite
app.command.NewLayer { tilemap = true, ask = false, gridBounds = Rectangle(0, 0, 2, 3) }
local layer, tileset = app.activeLayer, app.activeLayer.tileset
layer.name, tileset.name, tileset.baseIndex =
  "map", "terrain", tonumber(app.params.base_index or "37")
for index = 1, tonumber(app.params.tile_count or "5") - 1 do
  local key = app.params.tile_count and "tile-" .. index or ({ "a", "b", "c", "d" })[index]
  local tile = sprite:newTile(tileset)
  tile.image:clear(
    mode == ColorMode.RGB and app.pixelColor.rgba((10 + index) % 256, 30 + index // 256, 40, 255)
      or index
  )
  tile.data = "data-" .. index
  tile.color = Color { r = (20 + index) % 256, g = 30, b = 40, a = 255 }
  tile.properties.note = "default-" .. index
  tile.properties("example").large = 9007199254740993 + index
  tile.properties("example").point = Point(index, -index)
  -- Native string properties truncate at NUL; keep the opaque bytes nonzero.
  tile.properties("example").binary = string.char(255, 254, (index - 1) % 255 + 1)
  tile.properties("aigengame.spa").other = "retained-" .. index
  if app.params.unkeyed ~= tostring(index) then
    tile.properties("aigengame.spa").tile_key = app.params.duplicate == tostring(index) and "a"
      or key
  end
end
local image = Image(5, 1, ColorMode.TILEMAP)
local placements = json.decode(app.params.placements or "[1,2,3,4]")
for x, index in ipairs(placements) do
  image:putPixel(x - 1, 0, math.tointeger(index) | 0xe0000000)
end
image:putPixel(4, 0, 0xe0000000)
if app.params.unused then image:putPixel(tonumber(app.params.unused) - 1, 0, 0) end
if app.params.invalid then image:putPixel(0, 0, 99 | 0x80000000) end
sprite:newCel(layer, 1, image, Point(-3, 7))
app.activeLayer = layer
app.command.NewFrame { content = "cellinked" }
assert(layer:cel(1).image == layer:cel(2).image)
app.command.NewLayer { tilemap = true, ask = false, gridBounds = Rectangle(0, 0, 2, 3) }
local peer, generated = app.activeLayer, app.activeLayer.tileset
peer.name, peer.tileset = "peer", tileset
sprite:deleteTileset(generated)
sprite:newCel(peer, 2, Image(image), Point(4, -2))
local group = sprite:newGroup()
group.name = "nested"
peer.parent = group
local orphan = sprite:newTileset(Grid { x = 0, y = 0, width = 2, height = 3 }, 1)
orphan.name = "orphan"
for index, key in ipairs({ "x", "y" }) do
  local tile = sprite:newTile(orphan)
  tile.image:clear(
    mode == ColorMode.RGB and app.pixelColor.rgba(90 + index, 60, 30, 255)
      or mode == ColorMode.GRAY and app.pixelColor.graya(90 + index, 255)
      or index
  )
  tile.data = "orphan-data-" .. index
  tile.properties.note = "orphan-default-" .. index
  tile.properties("aigengame.spa").tile_key = key
  tile.properties("example").binary = string.char(255, 254, index)
end
assert(sprite:saveAs(app.params.source))
sprite:close()
