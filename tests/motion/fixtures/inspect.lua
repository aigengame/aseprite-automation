local sprite = assert(app.open(app.params.source))
local result = { frames = {}, cels = {}, transparent_index = sprite.transparentColor }
for _, frame in ipairs(sprite.frames) do
  result.frames[#result.frames + 1] = frame.duration
end
for _, cel in ipairs(sprite.cels) do
  local pixels, links = {}, {}
  for pixel in cel.image:pixels() do
    pixels[#pixels + 1] = pixel()
  end
  for index, other in ipairs(sprite.cels) do
    if other ~= cel and other.image == cel.image then links[#links + 1] = index end
  end
  result.cels[#result.cels + 1] = {
    frame = cel.frameNumber,
    layer = cel.layer.name,
    x = cel.position.x,
    y = cel.position.y,
    opacity = cel.opacity,
    z = cel.zIndex,
    width = cel.image.width,
    height = cel.image.height,
    pixels = pixels,
    links = links,
  }
end
local file = assert(io.open(app.params.out, "wb"))
file:write(json.encode(result))
file:close()
sprite:close()
