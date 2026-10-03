local mode = app.params.mode == "indexed" and ColorMode.INDEXED
  or app.params.mode == "grayscale" and ColorMode.GRAY
  or ColorMode.RGB
local sprite = Sprite(3, 2, mode)
sprite.layers[1].name = "Destination"
sprite:newEmptyFrame()
sprite:newEmptyFrame()
for _, cel in ipairs(sprite.cels) do
  sprite:deleteCel(cel)
end
if app.params.profile == "srgb" then
  sprite:assignColorSpace(ColorSpace { sRGB = true })
elseif app.params.profile == "icc" then
  sprite:assignColorSpace(ColorSpace { fromFile = app.params.icc })
else
  sprite:assignColorSpace(ColorSpace())
end
if mode == ColorMode.INDEXED then
  local palette = sprite.palettes[1]
  palette:resize(4)
  palette:setColor(0, Color { r = 0, g = 0, b = 0, a = 0 })
  palette:setColor(1, Color { r = 200, g = 20, b = 40, a = 255 })
  palette:setColor(2, Color { r = 10, g = 80, b = 160, a = 128 })
  palette:setColor(3, Color { r = 17, g = 31, b = 53, a = 255 })
  if app.params.palette then
    local entries = json.decode(app.params.palette)
    palette:resize(#entries)
    for index, rgba in ipairs(entries) do
      palette:setColor(index - 1, Color { r = rgba[1], g = rgba[2], b = rgba[3], a = rgba[4] })
    end
  end
  sprite.transparentColor = tonumber(app.params.mask or "0")
end
local layer = sprite.layers[1]
if app.params.occupied == "yes" or app.params.linked == "yes" then
  local image = Image(1, 1, mode)
  image:putPixel(0, 0, mode == ColorMode.INDEXED and 1 or app.pixelColor.rgba(12, 34, 56, 255))
  sprite:newCel(layer, app.params.linked and 1 or 2, image, Point(0, 0))
end
if app.params.linked == "yes" then
  app.activeSprite, app.activeLayer, app.activeFrame = sprite, layer, sprite.frames[1]
  app.command.NewFrame { content = "cellinked" }
  assert(layer:cel(1).image == layer:cel(2).image)
end
if app.params.target_kind == "group" then
  sprite:deleteLayer(layer)
  sprite:newGroup().name = "Destination"
elseif app.params.target_kind == "reference" then
  app.activeSprite, app.activeLayer = sprite, layer
  app.command.NewLayer { reference = true, ui = false }
  sprite:deleteLayer(layer)
  assert(sprite.layers[1].isReference)
elseif app.params.target_kind == "background" then
  app.activeSprite, app.activeLayer = sprite, layer
  app.command.BackgroundFromLayer()
end
assert(sprite:saveAs(app.params.out))
sprite:close()
