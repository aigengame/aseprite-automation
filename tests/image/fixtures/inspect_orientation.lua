local sprite = assert(app.open(app.params.source))
local layer = sprite.layers[tonumber(app.params.layer or "1")]
local result = {
  cels = {},
  transparent_color_index = sprite.transparentColor,
  is_reference = layer.isReference,
  is_background = layer.isBackground,
}
for _, cel in ipairs(layer.cels) do
  local image = cel.image
  local pixels = {}
  for pixel in image:pixels() do
    pixels[#pixels + 1] = pixel()
  end
  local links = {}
  for _, other in ipairs(layer.cels) do
    if other ~= cel and other.image == image then links[#links + 1] = other.frameNumber end
  end
  result.cels[#result.cels + 1] = {
    frame_number = cel.frameNumber,
    width = image.width,
    height = image.height,
    position = { x = cel.position.x, y = cel.position.y },
    pixels = pixels,
    linked_frames = links,
    opacity = cel.opacity,
    z_index = cel.zIndex,
  }
end
local file = assert(io.open(app.params.out, "wb"))
file:write(json.encode(result))
file:close()
sprite:close()
