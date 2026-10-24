-- Test-only native I/O interception around the unchanged packaged handler.
local request_file = assert(io.open(app.params.request, "rb"))
local input = json.decode(request_file:read("*a")).payload
request_file:close()
local staged = input.staged_sprite_file
local case = app.params.test_case
local ambient = Sprite(2, 2, ColorMode.RGB)
ambient:newEmptyFrame()
local layer, frame = ambient.layers[1], ambient.frames[2]
app.activeSprite, app.activeLayer, app.activeFrame = ambient, layer, frame
local sprite_mt = getmetatable(ambient)
local native_index, native_app = sprite_mt.__index, app
local saves, staged_opens = 0, 0
sprite_mt.__index = function(object, key)
  local value = native_index(object, key)
  if key == "saveAs" then
    return function(self, path)
      if path == staged then
        saves = saves + 1
        if case == "save" then return false end
      end
      return value(self, path)
    end
  end
  return value
end
app = setmetatable({
  open = function(path)
    if path == staged then
      staged_opens = staged_opens + 1
      if case == "reopen" and staged_opens == 1 then return nil end
      if case == "observation" and staged_opens == 2 then return nil end
    end
    local sprite = native_app.open(path)
    if path == staged and staged_opens == 1 and case == "comparison" then
      sprite.cels[1].image:putPixel(0, 0, app.pixelColor.rgba(255, 1, 2, 255))
    end
    return sprite
  end,
}, { __index = native_app, __newindex = function(_, key, value) native_app[key] = value end })
local ok, failure = pcall(dofile, app.params.test_handler)
app, sprite_mt.__index = native_app, native_index
local observations = {
  saves = saves,
  staged_opens = staged_opens,
  editor_restored = app.activeSprite == ambient
    and app.activeLayer == layer
    and app.activeFrame == frame,
  owned_sprites_closed = #app.sprites == 1 and ambient.isValid,
}
local out = assert(io.open(app.params.test_observations, "wb"))
out:write(json.encode(observations))
out:close()
ambient:close()
assert(ok, tostring(failure))
