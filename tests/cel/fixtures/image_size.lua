-- Independent native fixture and complete stored-pixel oracle for Cel Add.
local function create()
  local mode = app.params.mode
  local color_mode = mode == "rgb" and ColorMode.RGB
    or mode == "grayscale" and ColorMode.GRAY
    or ColorMode.INDEXED
  local sprite = Sprite(8, 6, color_mode)
  sprite:assignColorSpace(
    app.params.icc and ColorSpace { fromFile = app.params.icc } or ColorSpace { sRGB = true }
  )
  if color_mode == ColorMode.INDEXED then
    sprite.transparentColor = mode == "indexed7" and 7 or 0
    local palette = Palette(8)
    for index = 0, 7 do
      palette:setColor(index, Color { r = 20 + index, g = 60, b = 90, a = 255 })
    end
    sprite:setPalette(palette)
  end
  local spec = sprite.spec
  spec.width, spec.height = 2, 2
  local image = Image(spec)
  local pixel = color_mode == ColorMode.RGB and app.pixelColor.rgba(15, 40, 90, 255)
    or color_mode == ColorMode.GRAY and app.pixelColor.graya(80, 255)
    or 1
  image:drawPixel(0, 0, pixel)
  local layer = sprite.layers[1]
  layer.name, layer.data = "preserved", "Layer metadata"
  local original = sprite:newCel(layer, 1, image, Point(2, 1))
  original.opacity, original.zIndex = 200, 2
  app.activeSprite, app.activeLayer, app.activeFrame = sprite, layer, sprite.frames[1]
  app.command.NewFrame { content = "cellinked" }
  assert(layer:cel(1).image == layer:cel(2).image)
  sprite:newEmptyFrame(3)
  sprite.frames[2].duration = 0.23
  local tag = sprite:newTag(1, 2)
  tag.name = "preserved"
  local slice = sprite:newSlice(Rectangle(1, 1, 3, 2))
  slice.name, slice.data = "anchor", "Slice metadata"
  sprite.data = "Sprite metadata"
  assert(sprite:saveAs(app.params.out))
  sprite:close()
end

local function verify()
  local source = assert(app.open(app.params.source))
  local result = assert(app.open(app.params.result))
  assert(result.width == 8 and result.height == 6)
  assert(result.colorMode == source.colorMode and result.colorSpace == source.colorSpace)
  assert(result.transparentColor == source.transparentColor and result.data == source.data)
  assert(#result.layers == #source.layers and #result.frames == #source.frames)
  assert(#result.cels == #source.cels + 1)
  local layer, original_layer = result.layers[1], source.layers[1]
  assert(layer.name == original_layer.name and layer.data == original_layer.data)
  assert(layer.opacity == original_layer.opacity and layer.blendMode == original_layer.blendMode)
  assert(layer:cel(1).image == layer:cel(2).image)
  for number = 1, 2 do
    local before, after = original_layer:cel(number), layer:cel(number)
    assert(after.image.bytes == before.image.bytes)
    assert(after.image.width == before.image.width and after.image.height == before.image.height)
    assert(after.position == before.position and after.opacity == before.opacity)
    assert(after.zIndex == before.zIndex)
  end
  for number, frame in ipairs(source.frames) do
    assert(result.frames[number].duration == frame.duration)
  end
  assert(#result.tags == 1 and result.tags[1].name == source.tags[1].name)
  assert(result.tags[1].fromFrame.frameNumber == 1 and result.tags[1].toFrame.frameNumber == 2)
  assert(#result.slices == 1 and result.slices[1].bounds == source.slices[1].bounds)
  assert(result.slices[1].name == source.slices[1].name)
  assert(result.slices[1].data == source.slices[1].data)
  assert(#result.palettes == #source.palettes)
  for number = 1, #source.palettes do
    local palette = source.palettes[number]
    local actual = result.palettes[number]
    assert(#actual == #palette)
    for index = 0, #palette - 1 do
      assert(actual:getColor(index).rgbaPixel == palette:getColor(index).rgbaPixel)
    end
  end
  local added = assert(layer:cel(3))
  assert(added.image.width == tonumber(app.params.width))
  assert(added.image.height == tonumber(app.params.height))
  assert(added.position == Point(0, 0) and added.opacity == 255 and added.zIndex == 0)
  assert(added.image.colorMode == result.colorMode)
  -- The native file stores the Color Profile on the Sprite, not per Cel Image.
  assert(added.image.spec.colorSpace == original_layer:cel(1).image.spec.colorSpace)
  assert(added.image.spec.transparentColor == result.spec.transparentColor)
  for _, other in ipairs(result.cels) do
    assert(other == added or other.image ~= added.image)
  end
  local expected = result.colorMode == ColorMode.INDEXED and result.transparentColor or 0
  local checked = 0
  for pixel in added.image:pixels() do
    assert(pixel() == expected, "stored pixel differs from initial transparent value")
    checked = checked + 1
  end
  assert(checked == added.image.width * added.image.height)
  result:close()
  source:close()
end

if app.params.source then
  verify()
else
  create()
end
