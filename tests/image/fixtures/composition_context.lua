local composition = dofile(app.params.layer_composition)
local selector = dofile(app.params.layer_select)
local output_mode = assert(app.params.output_mode)
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
  local rendered = assert(composition.render(source, 1, requested, area, selector, {}, output_mode))
  assert(app.pixelColor.rgbaR(rendered:getPixel(0, 0)) == 255)
  assert(app.pixelColor.rgbaA(rendered:getPixel(0, 0)) == 128)
  assert(rendered.spec.colorSpace == source.spec.colorSpace)
  assert(preserved(ambient), "success changed ambient state")
  -- Fault injection after temporary visibility changes, while retaining real Layers.
  local unavailable_spec = { layers = source.layers, spec = false }
  local ok =
    pcall(composition.render, unavailable_spec, 1, requested, area, selector, {}, output_mode)
  assert(not ok)
  assert(preserved(ambient), "handled failure changed ambient state")
end
if output_mode == "preserve" then
  local indexed = Sprite(3, 1, ColorMode.INDEXED)
  local indexed_palette = Palette(8)
  indexed_palette:setColor(0, Color { r = 30, g = 40, b = 50, a = 255 })
  indexed_palette:setColor(7, Color { r = 0, g = 0, b = 0, a = 0 })
  indexed:setPalette(indexed_palette)
  indexed.transparentColor = 7
  local indexed_layer = indexed.layers[1]
  indexed_layer.name = "Ink"
  local indexed_group = indexed:newGroup()
  indexed_layer.parent = indexed_group
  indexed_group.isVisible, indexed_layer.isVisible = false, false
  local indexed_image = indexed_layer:cel(1).image
  indexed_image.bytes = string.char(0, 7, 3)
  local original_bytes = indexed_image.bytes
  local original_zero = indexed.palettes[1]:getColor(0)
  local original_mask = indexed.palettes[1]:getColor(7)
  app.activeSprite, app.activeLayer, app.activeFrame =
    sentinel, sentinel.layers[1], sentinel.frames[2]
  local include_group = { mode = "include", layers = { { layer_path = { 1 } } } }
  local function same_color(a, b)
    return a.red == b.red and a.green == b.green and a.blue == b.blue and a.alpha == b.alpha
  end
  local function indexed_preserved()
    local palette_now = indexed.palettes[1]
    return indexed.transparentColor == 7
      and indexed_image.bytes == original_bytes
      and same_color(palette_now:getColor(0), original_zero)
      and same_color(palette_now:getColor(7), original_mask)
      and not indexed_group.isVisible
      and not indexed_layer.isVisible
      and app.activeSprite == sentinel
  end
  local indexed_area = { x = 0, y = 0, width = 3, height = 1 }
  local rendered =
    assert(composition.render(indexed, 1, include_group, indexed_area, selector, {}, "preserve"))
  assert(rendered.bytes == original_bytes)
  assert(composition.missing_output_index(rendered, indexed.palettes[1]) == nil)
  assert(indexed_preserved(), "indexed success changed native state")
  local undefined_output = Image(2, 1, ColorMode.INDEXED)
  undefined_output.bytes = string.char(7, 8)
  local refused = assert(composition.missing_output_index(undefined_output, indexed.palettes[1]))
  assert(refused.rejection.code == "image_composition_unsupported")
  assert(refused.rejection.message:find("output Palette Index 8", 1, true))
  -- Invalid draw coordinates fail after temporary Layer, Image, Palette, and mask changes.
  local invalid_area = { x = "bad", y = 0, width = 3, height = 1 }
  local ok =
    pcall(composition.render, indexed, 1, include_group, invalid_area, selector, {}, "preserve")
  assert(not ok, "expected native rendering failure")
  assert(indexed_preserved(), "indexed failure changed native state")
  indexed:close()
end
local file = assert(io.open(app.params.out, "wb"))
file:write('{"success_restored":true,"failure_restored":true,"explicit_frame_and_roi":true}')
file:close()
source:close()
sentinel:close()
