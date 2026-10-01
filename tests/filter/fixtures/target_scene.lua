local mode = app.params.mode
local sprite = Sprite(4, 1, ColorMode.RGB)
local red = app.pixelColor.rgba
local first = sprite.layers[1]
first.name = "Editable"
first:cel(1).image:drawPixel(0, 0, red(100, 0, 0, 255))

if mode == "cartesian" then
  sprite:newEmptyFrame()
  sprite:newEmptyFrame()
  local third = Image(1, 1, ColorMode.RGB)
  third:drawPixel(0, 0, red(100, 0, 0, 255))
  sprite:newCel(first, 3, third, Point(0, 0))
  local second = sprite:newLayer()
  second.name = "Second"
  local image = Image(1, 1, ColorMode.RGB)
  image:drawPixel(0, 0, red(100, 0, 0, 255))
  sprite:newCel(second, 2, image, Point(0, 0))
elseif mode == "exclusions" then
  local function image_layer(name)
    local layer = sprite:newLayer()
    layer.name = name
    local image = Image(1, 1, ColorMode.RGB)
    image:drawPixel(0, 0, red(100, 0, 0, 255))
    sprite:newCel(layer, 1, image, Point(0, 0))
    return layer
  end
  image_layer("Hidden").isVisible = false
  image_layer("Locked").isEditable = false
  app.activeSprite, app.activeLayer = sprite, first
  assert(app.command.NewLayer { reference = true, ui = false })
  local reference = app.activeLayer
  reference.name = "Reference"
  local image = Image(1, 1, ColorMode.RGB)
  image:drawPixel(0, 0, red(100, 0, 0, 255))
  sprite:newCel(reference, 1, image, Point(0, 0))
  local group = sprite:newGroup()
  group.name = "Hidden Group"
  local child = image_layer("Child")
  child.parent = group
  group.isVisible = false
elseif mode == "linked" then
  app.activeSprite, app.activeLayer, app.activeFrame = sprite, first, sprite.frames[1]
  assert(app.command.NewFrame { content = "cellinked" })
  assert(first:cel(1).image == first:cel(2).image)
elseif mode == "selection" then
  local cel = first:cel(1)
  cel.position = Point(1, 0)
  local image = Image(2, 1, ColorMode.RGB)
  image:drawPixel(0, 0, red(100, 0, 0, 255))
  image:drawPixel(1, 0, red(200, 0, 0, 255))
  cel.image = image
else
  error("unknown target fixture mode")
end

assert(sprite:saveAs(app.params.source))
sprite:close()
