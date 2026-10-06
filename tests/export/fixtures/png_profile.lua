local images = dofile(app.params.export_image_support)
local identity = app.params.profile
local kind = identity == "none" and "none" or identity == "srgb" and "srgb" or "icc"
local source = kind == "none" and ColorSpace()
  or kind == "srgb" and ColorSpace { sRGB = true }
  or ColorSpace { fromFile = app.params.icc_file }
local names = kind == "icc" and { "", " ", string.rep("A", 80), "Original profile" }
  or { source.name }
for index, name in ipairs(names) do
  source.name = name
  local before = ColorSpace(source)
  local output = images.png_color_space(source, { kind = kind, icc_identity = identity })
  assert(source == before and source.name == name, "PNG preparation changed the input profile")
  assert(output == source, "PNG preparation changed the profile content")
  assert(output.name == (kind == "icc" and identity or name), "Unexpected PNG profile name")
  local spec = ImageSpec {
    width = 1,
    height = 1,
    colorMode = ColorMode.RGB,
  }
  spec.colorSpace = output
  local image = Image(spec)
  image:drawPixel(0, 0, app.pixelColor.rgba(31, 63, 127, 128))
  images.encode_image(image, app.params.directory .. "/profile-" .. index .. ".png")
end
local sprite = Sprite(1, 1, ColorMode.RGB)
sprite:saveAs(app.params.out)
sprite:close()
