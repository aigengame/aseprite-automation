-- Run the packaged static handler inside an editor with existing native context.
local native_dofile, native_app = dofile, app
local request = assert(io.open(app.params.request, "rb"))
local input = json.decode(request:read("a")).payload
request:close()
local profiles = native_dofile(app.params.color_profile)
local persistence = native_dofile(app.params.persistence)
local inspection = native_dofile(app.params.inspection)
local observed_source = assert(app.open(input.source_sprite_file))
profiles.restore_file_profile(observed_source, input.source_sprite_file)
local uuids = inspection.saved_layer_uuids(observed_source, input.source_sprite_file)
local source_before = profiles.snapshot(observed_source, uuids)
local ambient = Sprite(2, 2, ColorMode.RGB)
local ambient_layer = ambient:newLayer()
ambient:newEmptyFrame()
local ambient_frame = ambient.frames[2]
app.activeSprite, app.activeLayer, app.activeFrame = ambient, ambient_layer, ambient_frame
app.fgColor = Color { r = 3, g = 5, b = 7, a = 255 }
app.bgColor = Color { r = 11, g = 13, b = 17, a = 255 }
app.preferences.experimental.compose_groups = false
app.preferences.experimental.new_blend = true
local foreground, background = app.fgColor, app.bgColor
local ambient_before = profiles.snapshot(ambient, {})
local sprite_count = #app.sprites
local injected, profile_applied, palette_prepared = false, false, false
local rgba_written = false
local source_snapshots = {}

local function alter_context()
  native_app.fgColor = Color { r = 71, g = 73, b = 79, a = 255 }
  native_app.bgColor = Color { r = 83, g = 89, b = 97, a = 255 }
end

local fixture_environment
local function fixture_dofile(path)
  if path == app.params.export_image_pipeline then
    return assert(loadfile(path, "t", fixture_environment))()
  end
  local resource = native_dofile(path)
  if path == app.params.color_profile then
    local snapshot = resource.snapshot
    resource.snapshot = function(sprite, current_uuids)
      local facts = snapshot(sprite, current_uuids)
      if sprite.filename == input.source_sprite_file then
        source_snapshots[#source_snapshots + 1] = facts
      end
      return facts
    end
  elseif path == app.params.palette_quantization then
    local apply = resource.apply
    resource.apply = function(sprite, payload, current_uuids)
      local result = apply(sprite, payload, current_uuids)
      assert(not result.rejection, "Native Palette preparation did not complete")
      profile_applied = sprite.colorSpace == ColorSpace()
      palette_prepared = result.quantization.rendered_frames[1] == 1
        and #result.quantization.rendered_frames == 1
        and result.quantization.actual_colors <= payload.max_colors + 0
      if app.params.fault == "after_palette" then
        injected = true
        alter_context()
        error("injected static export failure after native Palette preparation")
      end
      return result
    end
  end
  return resource
end

local commands = setmetatable({}, { __index = native_app.command })
commands.SaveFileCopyAs = function(parameters)
  if app.params.fault == "encode" then
    assert(native_app.activeSprite.colorMode == ColorMode.INDEXED, "Conversion did not run")
    rgba_written = native_app.fs.isFile(input.staged_rgba_file)
    injected = true
    alter_context()
    error("injected static export native encoding failure")
  end
  return native_app.command.SaveFileCopyAs(parameters)
end
local fixture_app = setmetatable({ command = commands }, {
  __index = native_app,
  __newindex = function(_, key, value) native_app[key] = value end,
})
fixture_environment = setmetatable({ dofile = fixture_dofile, app = fixture_app }, { __index = _G })
assert(loadfile(app.params.production_handler, "t", fixture_environment))()

local report = {
  active_sprite_restored = app.activeSprite == ambient,
  active_layer_restored = app.activeLayer == ambient_layer,
  active_frame_restored = app.activeFrame == ambient_frame,
  foreground_restored = app.fgColor == foreground,
  background_restored = app.bgColor == background,
  compose_groups_restored = app.preferences.experimental.compose_groups == false,
  blend_preference_restored = app.preferences.experimental.new_blend == true,
  opened_sprites_released = #app.sprites == sprite_count,
  ambient_preserved = persistence.equal(ambient_before, profiles.snapshot(ambient, {})),
  source_preserved = persistence.equal(source_before, profiles.snapshot(observed_source, uuids)),
  source_snapshot_count = #source_snapshots,
  pipeline_source_preserved = #source_snapshots == 2
    and persistence.equal(source_snapshots[1], source_snapshots[2]),
  profile_applied = profile_applied,
  palette_prepared = palette_prepared,
  fault_injected = injected,
  rgba_written_during_fault = rgba_written,
}
local output = assert(io.open(app.params.context_report, "wb"))
output:write(json.encode(report))
output:close()
ambient:close()
observed_source:close()
