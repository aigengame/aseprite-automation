-- Native Despeckle owns samples, median, edges, Channels, and RGB Map quantization.
local module = {}
local application = dofile(app.params.filter_application)
local support = dofile(app.params.filter_support)

function module.apply(sprite, payload, uuids)
  local pixels = payload.pixels
  if pixels.color_mode == "indexed" and pixels.channels.kind == "components" then
    local green = false
    for _, name in ipairs(pixels.channels.names) do
      green = green or name == "green"
    end
    if not green then
      return support.reject(
        "This Despeckle slice requires Green in Indexed component Channels",
        true
      )
    end
  end
  local parameters = {}
  for name, value in pairs(pixels) do
    parameters[name] = value
  end
  parameters.kind = "pixels"
  local result = application.apply(
    sprite,
    { application = parameters },
    uuids,
    "Despeckle",
    function(flags)
      assert(
        app.command.Despeckle {
          ui = false,
          width = payload.width,
          height = payload.height,
          tiledMode = payload.tiled_mode,
          channels = flags,
        },
        "Native Despeckle failed"
      )
      return true
    end
  )
  if not result.rejection then
    result.width, result.height = payload.width, payload.height
    result.tiled_mode = payload.tiled_mode
    result.anchor = { x = math.floor(payload.width / 2), y = math.floor(payload.height / 2) }
    result.sample_count = payload.width * payload.height
  end
  return result
end

function module.observe_support()
  local sprite = nil
  local ok = pcall(function()
    for _, branch in ipairs { "rgb", "grayscale", "indexed", "indexed-components" } do
      local mode = branch == "indexed-components" and "indexed" or branch
      local modes = { rgb = ColorMode.RGB, grayscale = ColorMode.GRAY, indexed = ColorMode.INDEXED }
      sprite = Sprite(3, 1, modes[mode])
      local values = mode == "indexed" and { 3, 1, 2 } or { 100, 200, 40 }
      if branch == "indexed-components" then
        values = { 1, 2, 3 }
        local palette = Palette(7)
        local colors = {
          { 0, 0, 0, 0 },
          { 10, 100, 200, 255 },
          { 200, 50, 10, 255 },
          { 100, 200, 100, 255 },
          { 100, 50, 10, 255 },
          { 100, 0, 10, 255 },
          { 200, 100, 10, 255 },
        }
        for index, color in ipairs(colors) do
          palette:setColor(
            index - 1,
            Color { r = color[1], g = color[2], b = color[3], a = color[4] }
          )
        end
        sprite:setPalette(palette)
      end
      for x = 0, 2 do
        sprite.cels[1].image:drawPixel(
          x,
          0,
          mode == "indexed" and values[x + 1]
            or (
              mode == "grayscale" and app.pixelColor.graya(values[x + 1], 255)
              or app.pixelColor.rgba(values[x + 1], 20, 30, 255)
            )
        )
      end
      local channels = branch == "indexed" and { kind = "index" }
        or {
          kind = "components",
          names = {
            branch == "indexed-components" and "green" or (mode == "grayscale" and "gray" or "red"),
          },
        }
      local result = module.apply(sprite, {
        pixels = {
          color_mode = mode,
          channels = channels,
          cels_target = { kind = "all" },
          palette_frame_number = mode == "indexed" and 1 or nil,
        },
        width = 3,
        height = 1,
        tiled_mode = "none",
      })
      assert(not result.rejection)
      local expected = branch == "indexed-components" and 6
        or (
          mode == "indexed" and 2
          or (
            mode == "grayscale" and app.pixelColor.graya(100, 255)
            or app.pixelColor.rgba(100, 20, 30, 255)
          )
        )
      assert(sprite.cels[1].image:getPixel(1, 0) == expected)
      local path = app.fs.joinPath(app.params.workspace, "despeckle-probe.aseprite")
      assert(sprite:saveAs(path))
      sprite:close()
      sprite = assert(app.open(path))
      assert(sprite.cels[1].image:getPixel(1, 0) == expected)
      sprite:close()
      sprite = nil
    end
  end)
  if sprite then pcall(function() sprite:close() end) end
  return ok
end

return module
