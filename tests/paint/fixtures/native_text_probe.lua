-- Manual bounded investigation for issue #47, never a discovery-time probe.
-- Seed the font preference before PasteText to avoid the known fresh-pref crash.
assert(not app.isUIAvailable, "Run with --batch")
local kind = app.params.kind
assert(kind == "paste" or kind == "graphics", "Choose paste or graphics")
assert(app.params.font and app.fs.isFile(app.params.font), "Supply an existing font file")

local function nontransparent(image)
  local count = 0
  for pixel in image:pixels() do
    if app.pixelColor.rgbaA(pixel()) > 0 then count = count + 1 end
  end
  return count
end

local sprite = Sprite(96, 32, ColorMode.RGB)
app.activeSprite = sprite
local before = sprite.cels[1].image.bytes
local facts = {
  runtime = tostring(app.version),
  api = app.apiVersion,
  gui = app.isUIAvailable,
  kind = kind,
  initial_nontransparent = nontransparent(sprite.cels[1].image),
}
app.preferences.text_tool.font_face = app.params.font
local ok, err = pcall(function()
  if kind == "paste" then
    app.command.PasteText {
      ui = false,
      text = "SPA Test",
      fontName = app.params.font,
      fontSize = 12,
      color = Color { r = 255, g = 255, b = 255, a = 255 },
      x = 2,
      y = 2,
    }
  else
    local gc = sprite.cels[1].image.context
    gc.color = Color { r = 255, g = 255, b = 255, a = 255 }
    gc:fillText("SPA Test", 2, 2)
    local size = gc:measureText("SPA Test")
    facts.measured = { width = size.width, height = size.height }
  end
end)
facts.command_completed = ok
facts.error = tostring(err)
facts.changed = before ~= sprite.cels[1].image.bytes
facts.nontransparent = nontransparent(sprite.cels[1].image)
assert(sprite:saveAs(app.params.out))
sprite:close()
local reopened = assert(app.open(app.params.out))
facts.reopened_nontransparent = nontransparent(reopened.cels[1].image)
facts.reopened_bytes_match_initial = before == reopened.cels[1].image.bytes
reopened:close()

local control = Image(96, 32, ColorMode.RGB)
control.context.color = Color { r = 255, g = 255, b = 255, a = 255 }
control.context:fillRect(Rectangle(4, 4, 3, 2))
facts.control_rect_nontransparent = nontransparent(control)
print("SPA47_PROBE=" .. json.encode(facts))
