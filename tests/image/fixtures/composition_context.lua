local composition = dofile(app.params.layer_composition)
local selector = dofile(app.params.layer_select)
local source = Sprite(2, 2, ColorMode.RGB)
local group = source:newGroup()
group.opacity = 128
local child = source:newLayer()
child.parent = group
local image = Image(1, 1, ColorMode.RGB)
image:putPixel(0, 0, app.pixelColor.rgba(255, 0, 0, 255))
source:newCel(child, 1, image, Point(1, 1))
source:newEmptyFrame()
source:newCel(child, 2, Image(image), Point(0, 0))
group.isVisible, child.isVisible = false, false
source.selection:select(Rectangle(0, 0, 1, 1))
local sentinel = Sprite(1, 1, ColorMode.RGB)
sentinel:newEmptyFrame()
app.activeSprite, app.activeLayer, app.activeFrame =
  sentinel, sentinel.layers[1], sentinel.frames[2]
local requested = { mode = "include", layers = { { layer_path = { 2, 1 } } } }
local area = { x = 1, y = 1, width = 1, height = 1 }
local function preserved(ambient)
  return app.activeSprite == sentinel
    and app.activeLayer == sentinel.layers[1]
    and app.activeFrame == sentinel.frames[2]
    and app.preferences.experimental.compose_groups == ambient
    and not group.isVisible
    and not child.isVisible
    and source.selection.bounds.width == 1
    and source.selection.bounds.height == 1
end
for _, ambient in ipairs({ false, true }) do
  app.preferences.experimental.compose_groups = ambient
  local rendered = assert(composition.render(source, 1, requested, area, selector, {}))
  assert(app.pixelColor.rgbaR(rendered:getPixel(0, 0)) == 255)
  assert(app.pixelColor.rgbaA(rendered:getPixel(0, 0)) == 128)
  assert(preserved(ambient), "success changed ambient state")
  -- Fault injection after temporary visibility changes, while retaining real Layers.
  local unavailable_spec = { layers = source.layers, spec = false }
  local ok = pcall(composition.render, unavailable_spec, 1, requested, area, selector, {})
  assert(not ok)
  assert(preserved(ambient), "handled failure changed ambient state")
end
local file = assert(io.open(app.params.out, "wb"))
file:write('{"success_restored":true,"failure_restored":true,"explicit_frame_and_roi":true}')
file:close()
source:close()
sentinel:close()
