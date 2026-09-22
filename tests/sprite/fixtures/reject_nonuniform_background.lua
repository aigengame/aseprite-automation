local creation = dofile(assert(app.params.creation))
local target = assert(app.params.target)
local response = assert(app.params.response)
local requested = {
  kind = "background",
  background_color = { red=17, green=34, blue=51, alpha=255 },
}

local sprite = Sprite(3, 2, ColorMode.RGB)
app.activeSprite = sprite
app.activeLayer = sprite.layers[1]
app.activeFrame = sprite.frames[1]
app.bgColor = Color{ r=17, g=34, b=51, a=255 }
app.transaction("Create Background Layer", function()
  app.command.BackgroundFromLayer()
end)
sprite.layers[1].cels[1].image:putPixel(
  1, 0, app.pixelColor.rgba(200, 100, 50, 255)
)
assert(sprite:saveAs(target))
sprite:close()

local reopened = assert(app.open(target))
local accepted, message = pcall(function()
  creation.verify_persisted_initial_layer(reopened, requested)
end)
reopened:close()

local output = assert(io.open(response, "wb"))
output:write(json.encode({ accepted=accepted, message=tostring(message) }))
output:close()
