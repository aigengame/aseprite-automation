local transform = dofile(app.params.image_resize_transform)
local sentinel = Sprite(2, 2, ColorMode.RGB)
sentinel:newEmptyFrame()
local indexed = Sprite(2, 2, ColorMode.INDEXED)
local palette = Palette(2)
palette:setColor(0, Color { r = 0, g = 0, b = 0, a = 0 })
palette:setColor(1, Color { r = 255, g = 0, b = 0, a = 255 })
indexed:setPalette(palette)
local source = Image(indexed.layers[1]:cel(1).image)
source:putPixel(0, 0, 1)

local function state()
  return {
    sprite = app.activeSprite == sentinel,
    layer = app.activeLayer == sentinel.layers[1],
    frame = app.activeFrame == sentinel.frames[2],
  }
end

app.activeSprite = sentinel
app.activeLayer = sentinel.layers[1]
app.activeFrame = sentinel.frames[2]
local before = state()
local success, resized = pcall(
  function() return transform.resize(source, indexed, 3, 3, "bilinear", 1) end
)
local after_success = state()

local failure = pcall(
  function()
    transform.resize(
      { colorMode = ColorMode.INDEXED, fromFile = "missing" },
      indexed,
      3,
      3,
      "bilinear",
      1
    )
  end
)
local after_failure = state()

app.activeSprite = nil
local no_sprite_success = pcall(
  function() transform.resize(source, indexed, 3, 3, "bilinear", 1) end
)
local after_no_sprite = app.activeSprite == nil

local out = assert(io.open(app.params.out, "wb"))
out:write(json.encode({
  before = before,
  success = success,
  resized_width = success and resized.width or nil,
  after_success = after_success,
  failure = failure,
  after_failure = after_failure,
  no_sprite_success = no_sprite_success,
  after_no_sprite = after_no_sprite,
}))
out:close()
