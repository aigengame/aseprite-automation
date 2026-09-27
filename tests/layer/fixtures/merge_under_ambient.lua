local inspection = dofile(app.params.inspection)
local selection = dofile(app.params.layer_select)
local mutation = dofile(app.params.mutation)
local digest = dofile(app.params.digest)
local persistence = dofile(app.params.persistence)

local ambient = app.params.ambient == "true"
app.preferences.experimental.new_blend = ambient
local evidence = mutation.execute({
  operation = "merge",
  source_sprite_file = app.params.source,
  staged_sprite_file = app.params.target,
  target = { layer_path = { 2 } },
}, inspection, selection, digest, persistence)
assert(evidence.rejection == nil)
assert(evidence.persisted_reopen_verified)
assert(app.preferences.experimental.new_blend == ambient)

local reopened = assert(app.open(app.params.target))
local rendered = Image(reopened)
local pixel = rendered:getPixel(0, 0)
local result = {
  layer_count = #reopened.layers,
  lower_name = reopened.layers[1].name,
  ambient_restored = app.preferences.experimental.new_blend == ambient,
  first_pixel = {
    app.pixelColor.rgbaR(pixel),
    app.pixelColor.rgbaG(pixel),
    app.pixelColor.rgbaB(pixel),
    app.pixelColor.rgbaA(pixel),
  },
  after_digest = evidence.rendered_frames[1].after_digest,
}
reopened:close()
local report = assert(io.open(app.params.report, "wb"))
report:write(json.encode(result))
report:close()
