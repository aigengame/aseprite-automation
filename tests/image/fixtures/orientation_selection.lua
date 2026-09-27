local transform = dofile(app.params.image_orientation_transform)
local sprite = Sprite(12, 10, ColorMode.INDEXED)
local image = Image(3, 2, ColorMode.INDEXED)
for index = 0, 5 do
  image:putPixel(index % 3, index // 3, index + 1)
end
local target = sprite:newCel(sprite.layers[1], 1, image, Point(4, 5))
app.activeSprite = sprite
app.activeLayer = target.layer
app.activeFrame = sprite.frames[1]
sprite.selection = Selection(Rectangle(4, 5, 1, 1))
if app.params.operation == "flip" then
  transform.flip(target.image, app.params.axis)
else
  target.image = transform.rotate(target.image, tonumber(app.params.angle))
end
local pixels = {}
for pixel in target.image:pixels() do
  pixels[#pixels + 1] = pixel()
end
local bounds = sprite.selection.bounds
local out = assert(io.open(app.params.out, "wb"))
out:write(json.encode({
  pixels = pixels,
  selection = { x = bounds.x, y = bounds.y, width = bounds.width, height = bounds.height },
  same_context = app.activeSprite == sprite
    and app.activeLayer == target.layer
    and app.activeFrame == sprite.frames[1],
}))
out:close()
sprite:close()
