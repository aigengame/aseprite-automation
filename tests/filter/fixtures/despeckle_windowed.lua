-- Explicit local editor comparison; never called by headless pytest.
return function(case)
  assert(app.isUIAvailable, "Windowed Aseprite is required")
  local previous = app.activeSprite
  local sprite = assert(app.open(case.source))
  app.activeSprite, app.activeLayer, app.activeFrame = sprite, sprite.layers[1], sprite.frames[1]
  app.range:clear()
  app.range.colors = {}
  sprite.selection = Selection(Rectangle(0, 0, sprite.width, sprite.height))
  -- Inspect dimensions, edge controls and Channels in the dialog; click OK once.
  assert(app.command.Despeckle {
    ui = true,
    width = case.width,
    height = case.height,
    tiledMode = case.tiled_mode,
    channels = case.channels,
  })
  assert(sprite:saveAs(case.target))
  sprite:close()
  sprite = assert(app.open(case.target))
  sprite:close()
  local receipt = assert(io.open(case.receipt, "wb"))
  receipt:write(json.encode {
    is_ui_available = app.isUIAvailable,
    aseprite_version = tostring(app.version),
    source = case.source,
    target = case.target,
    reopened = true,
  })
  receipt:close()
  if previous then app.activeSprite = previous end
end
