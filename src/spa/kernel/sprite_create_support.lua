-- Sprite-owned creation semantics shared by the handler and capability probe.
local module = {}

local function rgba_from_pixel(image)
  local pixel = image:getPixel(0, 0)
  return {
    red = app.pixelColor.rgbaR(pixel),
    green = app.pixelColor.rgbaG(pixel),
    blue = app.pixelColor.rgbaB(pixel),
    alpha = app.pixelColor.rgbaA(pixel),
  }
end

local function persisted_initial_layer(sprite)
  assert(#sprite.layers == 1, "created Sprite does not have one Layer")
  local layer = sprite.layers[1]
  if layer.isBackground then
    assert(#layer.cels == 1, "created Background Layer does not have one Cel")
    return {
      kind = "background",
      background_color = rgba_from_pixel(layer.cels[1].image),
    }
  end
  assert(layer.isTransparent, "created Layer is neither Background nor transparent")
  return { kind = "transparent" }
end

local function restore_editor_state(previous)
  pcall(function() app.bgColor = previous.background_color end)
  if previous.sprite ~= nil and previous.sprite.isValid then
    pcall(function() app.activeSprite = previous.sprite end)
    pcall(function() app.activeLayer = previous.layer end)
    pcall(function() app.activeFrame = previous.frame end)
  end
end

function module.execute(payload, inspection)
  assert(payload.color_mode == "rgb", "unsupported Color Mode")
  assert(type(payload.width) == "number" and type(payload.height) == "number",
         "invalid Sprite dimensions")
  assert(type(payload.staged_sprite_file) == "string", "missing staged Sprite file")
  assert(payload.initial_layer ~= nil, "missing initial Layer choice")

  local previous = {
    sprite = app.activeSprite,
    layer = app.activeLayer,
    frame = app.activeFrame,
    background_color = app.bgColor,
  }
  local open_sprite = nil
  local ok, result = pcall(function()
    open_sprite = Sprite(payload.width, payload.height, ColorMode.RGB)
    if payload.initial_layer.kind == "background" then
      local color = assert(payload.initial_layer.background_color)
      app.activeSprite = open_sprite
      app.activeLayer = open_sprite.layers[1]
      app.activeFrame = open_sprite.frames[1]
      app.bgColor = Color{
        r=color.red, g=color.green, b=color.blue, a=color.alpha,
      }
      app.transaction("Create Background Layer", function()
        app.command.BackgroundFromLayer()
      end)
    else
      assert(payload.initial_layer.kind == "transparent",
             "invalid initial Layer choice")
    end

    assert(open_sprite:saveAs(payload.staged_sprite_file),
           "could not save staged Sprite")
    open_sprite:close()
    open_sprite = nil
    open_sprite = assert(app.open(payload.staged_sprite_file),
                         "could not reopen staged Sprite")
    local created = {
      sprite = inspection.inspect(open_sprite, payload.inspection_scope),
      persisted_initial_layer = persisted_initial_layer(open_sprite),
    }
    open_sprite:close()
    open_sprite = nil
    return created
  end)
  if open_sprite ~= nil then pcall(function() open_sprite:close() end) end
  restore_editor_state(previous)
  if not ok then error(result) end
  return result
end

return module
