local quantization = dofile(app.params.palette_quantization)

local target = Sprite(2, 1, ColorMode.RGB)
target.cels[1].image:drawPixel(0, 0, app.pixelColor.rgba(255, 0, 0, 255))
target.cels[1].image:drawPixel(1, 0, app.pixelColor.rgba(0, 0, 255, 255))

local sentinel = Sprite(2, 1, ColorMode.RGB)
sentinel:newEmptyFrame()
app.activeSprite = sentinel
app.activeLayer = sentinel.layers[1]
app.activeFrame = sentinel.frames[2]
app.range.colors = { 1, 3 }
local previous_blend = app.preferences.experimental.new_blend
app.preferences.experimental.new_blend = not previous_blend
local active_blend = app.preferences.experimental.new_blend

local function unchanged()
  assert(app.activeSprite == sentinel, "active Sprite was not restored")
  assert(app.activeLayer == sentinel.layers[1], "active Layer was not restored")
  assert(app.activeFrame == sentinel.frames[2], "active Frame was not restored")
  local picks = app.range.colors
  assert(#picks == 2 and picks[1] == 1 and picks[2] == 3, "Palette Picks were not restored")
  assert(
    app.preferences.experimental.new_blend == active_blend,
    "blending preference was not restored"
  )
end

local options = {
  palette_frame_number = "1",
  max_colors = "8",
  with_alpha = true,
  rgb_map_algorithm = "default",
  new_layer_blending_method = previous_blend,
}
local result = quantization.generate(target, options)
assert(not result.rejection and result.quantization.actual_colors > 0)
unchanged()

local ok, err = pcall(function()
  quantization.generate(
    target,
    options,
    function() error("injected native quantization failure") end
  )
end)
assert(not ok and tostring(err):find("injected native quantization failure", 1, true))
unchanged()

app.preferences.experimental.new_blend = previous_blend
target:close()
sentinel:close()
