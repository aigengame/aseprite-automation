local persistence = dofile(app.params.persistence)
local ambient = Sprite(2, 2, ColorMode.RGB)
local original = Sprite(3, 3, ColorMode.RGB)
original.useLayerUuids = true
local layer = original.layers[1]
layer.name = "subject"
layer:cel(1).image:putPixel(1, 1, app.pixelColor.rgba(17, 29, 41, 255))
layer:cel(1).position = Point(-2, 3)
layer:cel(1).opacity = 123
app.activeSprite, app.activeLayer, app.activeFrame = original, layer, original.frames[1]
app.command.NewFrame { content = "cellinked" }
local expected_pixels = layer:cel(1).image.bytes
local native_app, staged_opens, saves = app, 0, 0
-- Test-only observers delegate to real native objects. Save failure occurs before
-- writing; observation failure occurs after the UUID witness Sprite was opened.
local sprite_mt = getmetatable(original)
local native_index = sprite_mt.__index
sprite_mt.__index = function(object, key)
  local value = native_index(object, key)
  if object == original and key == "saveAs" then
    return function(self, path)
      saves = saves + 1
      if app.params.case == "save" then return false end
      return value(self, path)
    end
  end
  return value
end
app = setmetatable({
  open = function(path)
    if path == app.params.staged then
      staged_opens = staged_opens + 1
      if staged_opens == 1 and app.params.case == "reopen" then return nil end
    end
    local sprite = native_app.open(path)
    if path == app.params.staged then
      if staged_opens == 1 and app.params.case == "comparison" then
        sprite.cels[1].opacity = 12
      elseif staged_opens == 2 and app.params.case == "observation" then
        return setmetatable({ close = function() sprite:close() end }, {
          __index = function(_, key)
            if key == "layers" then error("injected UUID observation failure") end
            return sprite[key]
          end,
        })
      end
    end
    return sprite
  end,
}, { __index = native_app, __newindex = function(_, key, value) native_app[key] = value end })
local ok, reopened, uuids, facts =
  pcall(persistence.save_verified, original, app.params.staged, {}, "test")
app = native_app
sprite_mt.__index = native_index
assert(saves == 1, tostring(reopened))
if app.params.case ~= "success" then
  local reasons = {
    save = "could not save staged Sprite",
    reopen = "could not reopen staged Sprite",
    observation = "injected UUID observation failure",
    comparison = "persisted test differs",
  }
  assert(not ok and tostring(reopened):find(reasons[app.params.case], 1, true), tostring(reopened))
  assert(not original.isValid and #app.sprites == 1 and ambient.isValid, "owned Sprite leaked")
  ambient:close()
  return
end
assert(ok, tostring(reopened))
assert(staged_opens == 2) -- One reopen and one existing UUID witness observation.
assert(not original.isValid and reopened.isValid and reopened ~= original)
assert(#app.sprites == 2 and ambient.isValid)
assert(type(uuids["1"]) == "string" and uuids["1"] == tostring(reopened.layers[1].uuid))
assert(facts.layers[1].layer_uuid == uuids["1"])
assert(facts.metadata.frame_count == 2 and facts.metadata.cel_count == 2)
assert(facts.cels[1].bounds.x == -2 and facts.cels[1].bounds.y == 3)
assert(facts.cels[1].opacity == 123)
assert(reopened.cels[1].image.bytes == expected_pixels)
assert(reopened.cels[1].image == reopened.cels[2].image)
reopened:close()
assert(#app.sprites == 1 and ambient.isValid)
ambient:close()
