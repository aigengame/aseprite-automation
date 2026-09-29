-- Build independent Indexed targets; Frame Palette Changes are injected by Python.
local kind = assert(app.params.kind)
if kind == "helper" then
  local composite = dofile(assert(app.params.paint_composite))
  local target = Sprite(2, 1, ColorMode.INDEXED)
  target.transparentColor = 7
  local palette = Palette(9)
  for index = 0, 8 do
    palette:setColor(index, Color { r = index * 20, g = 0, b = 0, a = index == 7 and 0 or 255 })
  end
  target:setPalette(palette)
  local destination = assert(target.layers[1]:cel(1)).image
  destination:putPixel(0, 0, 1)
  destination:putPixel(1, 0, 1)
  local source = Image(destination)
  source:putPixel(0, 0, 7)
  source:putPixel(1, 0, 8)
  local sentinel = Sprite(1, 1, ColorMode.RGB)
  sentinel:newEmptyFrame()
  app.activeSprite = sentinel
  app.activeLayer = sentinel.layers[1]
  app.activeFrame = sentinel.frames[2]
  local prior = { sprite = app.activeSprite, layer = app.activeLayer, frame = app.activeFrame }
  local sprite_count = #app.sprites
  local palette_before = target.palettes[1]:getColor(8)

  local result = composite.draw_indexed(destination, source, { x = 0, y = 0 }, target.palettes[1])
  local successful = result:getPixel(0, 0) == 1
    and result:getPixel(1, 0) == 8
    and destination:getPixel(1, 0) == 1
    and #app.sprites == sprite_count
    and app.activeSprite == prior.sprite
    and app.activeLayer == prior.layer
    and app.activeFrame == prior.frame
  local ok = pcall(composite.draw_indexed, destination, source, nil, target.palettes[1])
  local palette_after = target.palettes[1]:getColor(8)
  local restored_after_error = not ok
    and #app.sprites == sprite_count
    and app.activeSprite == prior.sprite
    and app.activeLayer == prior.layer
    and app.activeFrame == prior.frame
    and destination:getPixel(1, 0) == 1
    and #target.palettes[1] == 9
    and palette_after.red == palette_before.red
    and palette_after.green == palette_before.green
    and palette_after.blue == palette_before.blue
    and palette_after.alpha == palette_before.alpha
  local output = assert(io.open(assert(app.params.out), "wb"))
  output:write(json.encode {
    successful = successful,
    restored_after_error = restored_after_error,
    open_sprite_count = sprite_count,
    error_thrown = not ok,
    open_sprite_count_after_error = #app.sprites,
    active_context_preserved = app.activeSprite == prior.sprite
      and app.activeLayer == prior.layer
      and app.activeFrame == prior.frame,
    target_preserved = destination:getPixel(1, 0) == 1,
    palette_preserved = #target.palettes[1] == 9
      and palette_after.red == palette_before.red
      and palette_after.green == palette_before.green
      and palette_after.blue == palette_before.blue
      and palette_after.alpha == palette_before.alpha,
  })
  output:close()
  sentinel:close()
  target:close()
  return
end

local sprite = Sprite(kind == "offset" and 4 or 2, 1, ColorMode.INDEXED)
sprite.transparentColor = 7
local palette_size = (kind == "background" or kind == "background-alpha") and 9
  or (kind == "missing-mask" and 7 or 8)
local palette = Palette(palette_size)
for index = 0, palette_size - 1 do
  palette:setColor(
    index,
    Color {
      r = index * 20,
      g = 0,
      b = 0,
      a = index == 7 and 0 or kind == "background-alpha" and index == 8 and 128 or 255,
    }
  )
end
sprite:setPalette(palette)
local layer = sprite.layers[1]
local first = assert(layer:cel(1))
if kind == "offset" then first.image = Image(first.image, Rectangle(0, 0, 2, 1)) end
first.image:putPixel(0, 0, 1)
first.image:putPixel(1, 0, 1)

if kind == "independent" or kind == "offset" then
  local frame = sprite:newEmptyFrame()
  sprite:newCel(layer, frame, Image(first.image), Point(kind == "offset" and 1 or 0, 0))
elseif kind == "linked" then
  layer.isContinuous = true
  sprite:newFrame(1)
  layer.isContinuous = false
  assert(layer:cel(2).image == first.image)
elseif kind == "background" or kind == "background-alpha" then
  app.activeSprite = sprite
  app.activeLayer = layer
  app.bgColor = Color(1)
  app.command.BackgroundFromLayer()
  assert(layer.isBackground)
elseif kind == "missing-mask" then
  assert(#sprite.palettes[1] == 7)
else
  error("unknown Indexed fixture kind")
end

assert(sprite:saveAs(assert(app.params.out)))
sprite:close()
