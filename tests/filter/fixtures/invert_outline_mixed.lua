-- Direct native witness for the command wrapper's one-time active-layer colors.
if app.params.action == "source" then
  local sprite = Sprite(5, 5, ColorMode.RGB)
  local background = sprite.layers[1]
  for p in background:cel(1).image:pixels() do
    p(app.pixelColor.rgba(19, 23, 29, 255))
  end
  background:cel(1).image:drawPixel(2, 2, app.pixelColor.rgba(31, 79, 137, 255))
  assert(app.command.BackgroundFromLayer())
  background.name = "Background"
  if app.params.only ~= "true" then
    local ordinary = sprite:newLayer()
    ordinary.name = "Ordinary"
    local image = Image(5, 5, ColorMode.RGB)
    for p in image:pixels() do
      p(app.pixelColor.rgba(19, 23, 29, 0))
    end
    image:drawPixel(2, 2, app.pixelColor.rgba(19, 23, 29, 255))
    sprite:newCel(ordinary, 1, image)
  end
  assert(sprite:saveAs(app.params.source))
  sprite:close()
else
  local sprite = assert(app.open(app.params.source))
  app.activeSprite = sprite
  app.activeLayer = sprite.layers[#sprite.layers]
  app.activeFrame = sprite.frames[1]
  app.range:clear()
  app.range.layers = sprite.layers
  app.range.frames = { 1 }
  app.range.colors = {}
  sprite.selection = Selection(Rectangle(0, 0, 5, 5))
  assert(app.command.Outline {
    ui = false,
    channels = 7,
    place = 1,
    matrix = 170,
    tiledMode = 0,
    color = Color { r = 211, g = 157, b = 89, a = 203 },
    bgColor = Color { r = 19, g = 23, b = 29, a = 0 },
  })
  assert(sprite:saveAs(app.params.target))
  sprite:close()
end
