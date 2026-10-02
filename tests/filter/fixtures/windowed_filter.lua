-- Operator-assisted oracle. This file is deliberately not run by batch pytest.
return function(case)
  assert(app.isUIAvailable, "Windowed Aseprite is required")
  local sprite = assert(app.open(case.source))
  local layer = sprite.layers[1]
  app.activeCel = assert(layer:cel(case.basis))
  assert(app.site.tilesetMode == TilesetMode.MANUAL, "Select Manual Tileset mode first")
  assert(app.command.Timeline { open = true })
  local selection = Selection()
  if case.selection.kind == "mask" then
    for _, row in ipairs(case.selection.rows) do
      for _, run in ipairs(row.runs) do
        selection:add(Rectangle(run.x, row.y, run.length, 1))
      end
    end
  else
    local r = case.selection.rectangle
    selection:add(Rectangle(r.x, r.y, r.width, r.height))
  end
  sprite.selection = selection
  app.range:clear()
  if case.palette then
    -- UIContext exposes Color Bar picks only while the Timeline range is clear.
    app.range.colors = { 1 }
  else
    local frames = {}
    -- json.decode arrays are userdata; Range setters require actual Lua tables.
    for _, frame in ipairs(case.frames) do
      frames[#frames + 1] = frame
    end
    app.range.layers = { layer }
    app.range.frames = frames
  end
  local receipt = {
    name = case.name,
    version = tostring(app.version),
    is_ui_available = app.isUIAvailable,
    tileset_mode = "manual",
    active_frame = app.activeFrame.frameNumber,
    frames = {},
    colors = app.range.colors,
    selection_pixels = 0,
  }
  for _, frame in ipairs(app.range.frames) do
    receipt.frames[#receipt.frames + 1] = frame.frameNumber
  end
  assert(#receipt.frames == #case.frames, "Unexpected Timeline range")
  for i, frame in ipairs(case.frames) do
    assert(receipt.frames[i] == frame, "Unexpected Timeline frame")
  end
  assert(#app.range.layers == 1 and app.range.layers[1] == layer, "Unexpected target Layer")
  assert(#app.range.cels == #case.frames, "Unexpected target Cels")
  assert(receipt.active_frame == case.basis, "Unexpected active Palette frame")
  assert(#receipt.colors == (case.palette and 1 or 0), "Unexpected Palette Picks")
  if case.palette then assert(receipt.colors[1] == 1) end
  for y = 0, sprite.height - 1 do
    for x = 0, sprite.width - 1 do
      assert(sprite.selection:contains(x, y) == selection:contains(x, y))
      if sprite.selection:contains(x, y) then
        receipt.selection_pixels = receipt.selection_pixels + 1
      end
    end
  end
  -- Enter Brightness 50 in the real dialog; keep Contrast 0 and Cels Selected.
  -- Only click OK once. The Python comparison detects Cancel or repeated Apply.
  assert(app.command.BrightnessContrast {
    ui = true,
    channels = FilterChannels[case.channel],
    brightness = 0,
    contrast = 0,
  })
  assert(sprite:saveAs(case.target))
  sprite:close()
  local reopened = assert(app.open(case.target))
  reopened:close()
  receipt.reopened = true
  local output = assert(io.open(case.receipt, "wb"))
  output:write(json.encode(receipt))
  output:close()
end
