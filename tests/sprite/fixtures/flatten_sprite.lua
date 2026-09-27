local mode = app.params.mode or "rgb"
assert(mode == "rgb" or mode == "indexed")
local color_mode = mode == "indexed" and ColorMode.INDEXED or ColorMode.RGB
local sprite = Sprite(3, 2, color_mode)
sprite.useLayerUuids = true
if mode == "indexed" then
  local palette = Palette(3)
  palette:setColor(0, Color { r = 0, g = 0, b = 0, a = 0 })
  palette:setColor(1, Color { r = 255, g = 0, b = 0, a = 255 })
  palette:setColor(2, Color { r = 0, g = 0, b = 255, a = 255 })
  sprite:setPalette(palette)
end
sprite:newEmptyFrame()
local effects = sprite:newLayer()
effects.name = "effects"
local red = Image(1, 1, color_mode)
red:drawPixel(0, 0, mode == "indexed" and 1 or app.pixelColor.rgba(255, 0, 0, 255))
sprite:newCel(effects, 1, red, Point(1, 0))
local blue = Image(1, 1, color_mode)
blue:drawPixel(0, 0, mode == "indexed" and 2 or app.pixelColor.rgba(0, 0, 255, 255))
sprite:newCel(effects, 2, blue, Point(1, 1))
local tag = sprite:newTag(1, 2)
tag.name = "action"
local slice = sprite:newSlice(Rectangle(0, 0, 2, 2))
slice.name = "focus"
assert(sprite:saveAs(app.params.out))
sprite:close()
