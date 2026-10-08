-- Exercise the unchanged handler in an editor that already has active context.
local native_dofile = dofile
local file = assert(io.open(app.params.request, "rb"))
local input = json.decode(file:read("a")).payload
file:close()
local ambient = Sprite(2, 2, ColorMode.RGB)
local layer = ambient:newLayer()
ambient:newEmptyFrame()
local frame = ambient.frames[2]
app.activeSprite, app.activeLayer, app.activeFrame = ambient, layer, frame
local original_pixels = ambient.layers[1]:cel(1).image.bytes
local sprite_count = #app.sprites
local native_preferences = app.preferences.color
native_preferences.manage = true
native_preferences.working_rgb_space =
  ColorSpace { fromFile = app.params.profile_display_p3_cc0 }.name
native_preferences.files_with_profile = 2 -- CONVERT
native_preferences.missing_profile = 3 -- ASSIGN
local expected_preferences = {
  manage = native_preferences.manage,
  working_rgb_space = native_preferences.working_rgb_space,
  files_with_profile = native_preferences.files_with_profile,
  missing_profile = native_preferences.missing_profile,
}
local injected = false
local stage_written = false
local before_pixel, after_pixel = nil, nil

-- Wrap only test-local instances of the existing profile resource. The native
-- handler, transaction, save/reopen, evidence checks, and cleanup remain fixed.
local function fixture_dofile(resource_path)
  local resource = native_dofile(resource_path)
  if resource_path == app.params.color_profile then
    if app.params.fault == "post_mutation" then
      local snapshot, calls = resource.snapshot, 0
      resource.snapshot = function(sprite, uuids)
        calls = calls + 1
        if calls == 2 then
          local created = assert(sprite.layers[1]:cel(2), "No native import to interrupt")
          assert(created.image.width == input.decoded.width)
          assert(created.image.bytes ~= "")
          injected = true
          error("injected error after native newCel")
        end
        return snapshot(sprite, uuids)
      end
    elseif app.params.fault == "reopen_loss" then
      local restore = resource.restore_file_profile
      resource.restore_file_profile = function(sprite, path)
        local result = restore(sprite, path)
        if path == input.staged_sprite_file then
          local image = assert(sprite.layers[1]:cel(2)).image
          before_pixel = image:getPixel(0, 0)
          image:putPixel(0, 0, app.pixelColor.rgba(201, 151, 101, 255))
          after_pixel = image:getPixel(0, 0)
          assert(before_pixel ~= after_pixel, "Fault did not change reopened pixels")
          assert(sprite:saveAs(path), "Could not persist injected pixel loss")
          injected = true
          stage_written = app.fs.isFile(path)
        end
        return result
      end
    end
  end
  return resource
end
local fixture_environment = setmetatable({ dofile = fixture_dofile }, { __index = _G })
assert(loadfile(app.params.production_handler, "t", fixture_environment))()
local state = {
  active_sprite_restored = app.activeSprite == ambient,
  active_layer_restored = app.activeLayer == layer,
  active_frame_restored = app.activeFrame == frame,
  ambient_pixels_preserved = ambient.layers[1]:cel(1).image.bytes == original_pixels,
  opened_sprites_released = #app.sprites == sprite_count,
  preferences_before = expected_preferences,
  preferences_after = {
    manage = native_preferences.manage,
    working_rgb_space = native_preferences.working_rgb_space,
    files_with_profile = native_preferences.files_with_profile,
    missing_profile = native_preferences.missing_profile,
  },
  fault_injected = injected,
  stage_written = stage_written,
  before_pixel = before_pixel,
  after_pixel = after_pixel,
}
local report = assert(io.open(app.params.context_report, "wb"))
report:write(json.encode(state))
report:close()
ambient:close()
