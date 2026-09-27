local sprite = assert(app.open(app.params.source))
local frame_number = tonumber(assert(app.params.frame))
local image = assert(sprite.layers[1]:cel(frame_number)).image
local pixel = image:getPixel(tonumber(app.params.x), tonumber(app.params.y))
local result = { pixel = pixel, width = image.width, height = image.height }
if app.params.row == "true" then
  result.row = {}
  for x = 0, image.width - 1 do
    result.row[#result.row + 1] = image:getPixel(x, tonumber(app.params.y))
  end
  if image.colorMode == ColorMode.INDEXED then
    result.transparent_index = sprite.transparentColor
    local hidden = sprite.palettes[1]:getColor(sprite.transparentColor)
    result.transparent_entry = {
      red = hidden.red,
      green = hidden.green,
      blue = hidden.blue,
      alpha = hidden.alpha,
    }
  end
end
if image.colorMode == ColorMode.GRAY then
  result.gray = app.pixelColor.grayaV(pixel)
  result.alpha = app.pixelColor.grayaA(pixel)
elseif image.colorMode == ColorMode.INDEXED then
  result.transparent_index = sprite.transparentColor
  local palette = sprite.palettes[1]
  local color = palette:getColor(pixel)
  result.palette_color = {
    red = color.red,
    green = color.green,
    blue = color.blue,
    alpha = color.alpha,
  }
else
  result.red = app.pixelColor.rgbaR(pixel)
  result.green = app.pixelColor.rgbaG(pixel)
  result.blue = app.pixelColor.rgbaB(pixel)
  result.alpha = app.pixelColor.rgbaA(pixel)
end
local file = assert(io.open(app.params.out, "wb"))
file:write(json.encode(result))
file:close()
sprite:close()
