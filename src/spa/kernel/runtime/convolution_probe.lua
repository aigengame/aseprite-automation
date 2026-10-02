-- Observe the selected native Resource path without publishing an Operation.
local module = {}

function module.observe()
  local observations = {}
  local sprite
  local function rgba(pixel)
    return {
      app.pixelColor.rgbaR(pixel),
      app.pixelColor.rgbaG(pixel),
      app.pixelColor.rgbaB(pixel),
      app.pixelColor.rgbaA(pixel),
    }
  end
  for _, case in ipairs {
    { "brightness", "red", FilterChannels.RED },
    { "brightness", "alpha", FilterChannels.ALPHA },
    { "__spa_missing_convolution_probe__", "red", FilterChannels.RED },
  } do
    local ok = pcall(function()
      sprite = Sprite(1, 1, ColorMode.RGB)
      app.activeSprite = sprite
      app.range:clear()
      sprite.selection = Selection(Rectangle(0, 0, 1, 1))
      sprite.cels[1].image:putPixel(0, 0, app.pixelColor.rgba(10, 20, 30, 40))
      local completed = app.command.ConvolutionMatrix {
        ui = false,
        fromResource = case[1],
        channels = case[3],
        tiledMode = "none",
      }
      local after = rgba(sprite.cels[1].image:getPixel(0, 0))
      local path = app.fs.joinPath(app.params.workspace, "convolution-probe.aseprite")
      assert(sprite:saveAs(path))
      sprite:close()
      sprite = assert(app.open(path))
      observations[#observations + 1] = {
        resource_name = case[1],
        requested_channel = case[2],
        command_completed = completed == true,
        before_rgba = { 10, 20, 30, 40 },
        after_rgba = after,
        reopened_rgba = rgba(sprite.cels[1].image:getPixel(0, 0)),
      }
    end)
    if sprite then pcall(function() sprite:close() end) end
    sprite = nil
    -- Partial evidence remains useful. It cannot grant callable capability.
    if not ok then break end
  end
  return observations
end

return module
