-- Native Eraser parity when the Sprite mask has no Palette Entry.
if app.params.target then
  local reference = assert(app.open(app.params.reference))
  local target = assert(app.open(app.params.target))
  assert(target.transparentColor == 7 and #target.palettes[1] == 2)
  assert(#target.frames == #reference.frames)
  for frame = 1, #reference.frames do
    local expected = assert(reference.layers[1]:cel(frame))
    local actual = assert(target.layers[1]:cel(frame))
    assert(actual.image.width == 3 and actual.image.height == 1)
    assert(actual.position == expected.position)
    assert(actual.image.bytes == expected.image.bytes)
  end
  if #target.frames == 2 then
    assert(target.layers[1]:cel(1).image == target.layers[1]:cel(2).image)
  end
  for index = 0, 1 do
    assert(target.palettes[1]:getColor(index) == reference.palettes[1]:getColor(index))
  end
  target:close()
  reference:close()
  return
end

local sprite = Sprite(3, 1, ColorMode.INDEXED)
local palette = Palette(2)
palette:setColor(0, Color { r = 0, g = 0, b = 0, a = 255 })
palette:setColor(1, Color { r = 255, g = 0, b = 0, a = 255 })
sprite:setPalette(palette)
sprite.transparentColor = 7
local layer = sprite.layers[1]
layer:cel(1).image:clear(1)
if app.params.linked == "true" then
  layer.isContinuous = true
  sprite:newFrame(1)
  layer.isContinuous = false
end
assert(sprite:saveAs(app.params.source))
sprite:close()

-- Reopen the saved Source, then use the editor Tool without SPA's Paint helpers.
sprite = assert(app.open(app.params.source))
assert(sprite.transparentColor == 7 and #sprite.palettes[1] == 2)
app.useTool {
  tool = "eraser",
  cel = sprite.layers[1]:cel(1),
  layer = sprite.layers[1],
  frame = sprite.frames[1],
  brush = Brush { type = BrushType.CIRCLE, size = 1 },
  opacity = 255,
  freehandAlgorithm = 0,
  button = MouseButton.LEFT,
  points = { Point(1, 0) },
}
assert(sprite.layers[1]:cel(1).image:getPixel(1, 0) == 7)
assert(sprite:saveAs(app.params.reference))
sprite:close()
sprite = assert(app.open(app.params.reference))
assert(sprite.transparentColor == 7 and #sprite.palettes[1] == 2)
assert(sprite.layers[1]:cel(1).image:getPixel(1, 0) == 7)
sprite:close()
