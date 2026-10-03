local sprite = Sprite(8, 8, ColorMode.RGB)
sprite:newEmptyFrame()
for _, color in ipairs {
  Color { r = 12, g = 34, b = 56, a = 78 },
  Color { r = 0, g = 0, b = 0, a = 0 },
} do
  local slice = sprite:newSlice(Rectangle(1, 2, 3, 4))
  slice.name, slice.data, slice.color = "same", "same", color
end
assert(sprite:saveAs(app.params.out))
sprite:close()
