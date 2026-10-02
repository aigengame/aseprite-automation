local filter = dofile(
  app.params.invert_color
    or app.params.outline
    or app.params.hue_saturation
    or app.params.brightness_contrast
)
local kind = app.params.kind
local failing = app.params.fault == "true"
local mode = kind == "palette" and ColorMode.INDEXED or ColorMode.RGB
local target = Sprite(3, 1, mode)
target:newEmptyFrame(2)
target.layers[1].name = "Target Ink"
local target_image = target.layers[1]:cel(1).image
if kind == "palette" then
  target.palettes[1]:setColor(1, Color { r = 80, g = 40, b = 20, a = 255 })
  target_image:putPixel(0, 0, 1)
else
  target_image:putPixel(0, 0, app.pixelColor.rgba(80, 40, 20, 255))
end
local tile
if kind == "tilemap" then
  target.gridBounds = Rectangle(0, 0, 1, 1)
  app.command.NewLayer { tilemap = true, ui = false }
  local tilemap = app.activeLayer
  tile = target:newTile(tilemap.tileset)
  tile.image:putPixel(0, 0, app.pixelColor.rgba(80, 40, 20, 255))
  tile.properties("other.plugin").retained = "original"
  local map = Image(1, 1, ColorMode.TILEMAP)
  map:putPixel(0, 0, 1)
  target:newCel(tilemap, 1, map)
end
local target_selection = Selection(Rectangle(0, 0, 3, 1))
target_selection:subtract(Rectangle(1, 0, 1, 1))
target.selection = target_selection

local prior = Sprite(2, 1, ColorMode.RGB)
prior:newEmptyFrame(2)
local prior_layer = prior:newLayer()
app.activeSprite = prior
app.activeLayer = prior_layer
app.activeFrame = prior.frames[2]
app.range:clear()
app.range.layers = { prior.layers[1], prior_layer }
app.range.frames = { 1, 2 }
app.range.colors = { 1, 3 }
prior.selection = Selection(Rectangle(1, 0, 1, 1))

local function state()
  local image_bytes = {}
  local contents = target.layers[1]:cel(1).image.bytes
  for index = 1, #contents do
    image_bytes[#image_bytes + 1] = string.byte(contents, index)
  end
  local selected = {}
  for x = 0, 2 do
    selected[#selected + 1] = target.selection:contains(x, 0)
  end
  local prior_selected = {}
  for x = 0, 1 do
    prior_selected[#prior_selected + 1] = prior.selection:contains(x, 0)
  end
  local layer_ids, frames, colors = {}, {}, {}
  for _, layer in ipairs(app.range.layers) do
    layer_ids[#layer_ids + 1] = layer.id
  end
  for _, frame in ipairs(app.range.frames) do
    frames[#frames + 1] = frame.frameNumber
  end
  for _, color in ipairs(app.range.colors) do
    colors[#colors + 1] = color
  end
  return {
    active_sprite_id = app.activeSprite.id,
    active_layer_id = app.activeLayer.id,
    active_frame_number = app.activeFrame.frameNumber,
    range_layer_ids = layer_ids,
    range_frames = frames,
    range_colors = colors,
    target_selection = selected,
    prior_selection = prior_selected,
    target_image_bytes = image_bytes,
    palette_red = target.palettes[1]:getColor(1).red,
    tile_pixel = tile and tile.image:getPixel(0, 0) or nil,
    tile_property = tile and tile.properties("other.plugin").retained or nil,
  }
end

local before = state()
_G.SPA_TEST_TARGET = target
_G.SPA_TEST_INITIAL_IMAGE_BYTES = target.layers[1]:cel(1).image.bytes
local application
if kind == "palette" then
  application = {
    kind = "indexed-palette-entries",
    palette_frame_number = 1,
    entries = { kind = "selected", indexes = { 1 } },
    channels = { kind = "components", names = { "red" } },
  }
else
  application = {
    kind = "pixels",
    color_mode = "rgb",
    cels_target = { kind = "selected", layers = { { layer_path = { 1 } } }, frame_numbers = { 1 } },
    channels = { kind = "components", names = { "red" } },
  }
end
if kind == "tilemap" then
  application.cels_target = { kind = "all" }
  application.tileset_mode = "manual"
end
local ok, value = pcall(function()
  local payload = {
    application = application,
    brightness = 50,
    contrast = 0,
    tilemap_manual_filter_available = true,
  }
  if app.params.hue_saturation then
    payload = {
      application = application,
      adjustment = { mode = "hsl-multiply", hue = 0, saturation = 0, lightness = 50 },
    }
  end
  if app.params.invert_color or app.params.outline then
    payload = application
    payload.kind = nil
    if app.params.outline then
      payload.place = "inside"
      payload.matrix = { kind = "preset", name = "circle" }
      payload.tiled_mode = "none"
      payload.outline_color = { kind = "rgba", red = 210, green = 0, blue = 0, alpha = 255 }
      payload.background_color = { kind = "rgba", red = 0, green = 0, blue = 0, alpha = 0 }
    end
  end
  return filter.apply(target, payload, {})
end)
local after = state()
local error_message = nil
if not ok then error_message = tostring(value) end
local response = {
  kind = kind,
  fault = failing,
  success = ok,
  native_effect_observed = _G.SPA_TEST_NATIVE_EFFECT_OBSERVED == true,
  error = error_message,
  before = before,
  after = after,
}
local file = assert(io.open(app.params.response, "wb"))
file:write(json.encode(response))
file:close()
