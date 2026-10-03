-- Exercise the packaged reader with real native export, then alter its output.
local native_app = app
local inspection = dofile(app.params.inspection)
local sprite = assert(app.open(app.params.source))
local mode = app.params.mode or "duplicate_frames"
if mode == "keyless" then
  local empty = sprite:newSlice()
  empty.name = "keyless"
  empty.data = "native empty Slice"
end
app.activeFrame = sprite.frames[4]
local baseline = inspection.inspect(sprite, { "slices" }).slices
local commands = native_app.command
local function plain(value)
  if type(value) ~= "userdata" then return value end
  local result = {}
  if tostring(value):sub(1, 1) == "[" then
    for index = 1, #value do
      result[index] = plain(value[index])
    end
  else
    for key, item in pairs(value) do
      result[key] = plain(item)
    end
  end
  return result
end
local wrapped = {
  ExportSpriteSheet = function(options)
    if mode == "no_write" then return end
    if mode == "native_line_feed" then sprite.slices[1].data = "line\nbreak" end
    commands.ExportSpriteSheet(options)
    if mode == "native_line_feed" then return end
    local file = assert(io.open(options.dataFilename, "rb"))
    local vendor = plain(json.decode(file:read("*a")))
    file:close()
    local multi
    local colored
    for _, value in ipairs(vendor.meta.slices) do
      if value.name == "multi" then multi = value end
      if value.color then colored = value end
    end
    if mode == "duplicate_frames" then
      multi.keys[2].frame = multi.keys[1].frame
    elseif mode == "unordered_frames" then
      multi.keys[2], multi.keys[3] = multi.keys[3], multi.keys[2]
    elseif mode == "fractional_frame" then
      multi.keys[2].frame = 2.5
    elseif mode == "outside_frame" then
      multi.keys[3].frame = #sprite.frames
    elseif mode == "fractional_rectangle" then
      multi.keys[1].bounds.x = 1.5
    elseif mode == "negative_dimensions" then
      multi.keys[1].bounds.w = -1
    elseif mode == "fractional_pivot" then
      multi.keys[1].pivot.y = 1.5
    elseif mode == "rectangle_array" then
      multi.keys[1].bounds = { 1, 2, 3, 4 }
    elseif mode == "keys_object" then
      multi.keys = { ["1"] = multi.keys[1], ["2"] = multi.keys[2], ["3"] = multi.keys[3] }
    elseif mode == "slices_object" then
      local object = {}
      for index, value in ipairs(vendor.meta.slices) do
        object[tostring(index)] = value
      end
      vendor.meta.slices = object
    elseif mode == "missing_keys" then
      multi.keys = nil
    elseif mode == "missing_first_key" then
      table.remove(multi.keys, 1)
    elseif mode == "missing_first_center" then
      multi.keys[1].center = nil
    elseif mode == "missing_first_pivot" then
      multi.keys[1].pivot = nil
    elseif mode == "different_first_bounds" then
      multi.keys[1].bounds.w = multi.keys[1].bounds.w + 1
    elseif mode == "null_center" then
      multi.keys[1].center = json.decode("null")
    elseif mode == "bad_data_type" then
      multi.data = 7
    elseif mode == "different_data" then
      multi.data = "invented"
    elseif mode == "bad_color" then
      colored.color = "red"
    elseif mode == "different_color" then
      colored.color = "#000000ff"
    elseif mode == "missing_color" then
      colored.color = nil
    end
    file = assert(io.open(options.dataFilename, "wb"))
    file:write(json.encode(vendor))
    file:close()
  end,
}
app = setmetatable({ command = setmetatable(wrapped, { __index = commands }) }, {
  __index = function(_, key) return native_app[key] end,
  __newindex = function(_, key, value) native_app[key] = value end,
})
local ok, result = pcall(inspection.inspect, sprite, { "slices" })
local file = assert(io.open(app.params.output, "wb"))
file:write(json.encode({
  baseline = baseline,
  accepted = ok,
  result = result,
  active_sprite_preserved = native_app.activeSprite == sprite,
  active_frame_number = native_app.activeFrame.frameNumber,
}))
file:close()
