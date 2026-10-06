-- Native GIF composition and encoding; callers verify and publish staged files.
local module = {}
local composition = dofile(assert(app.params.layer_composition))
local selection = dofile(assert(app.params.layer_select))
local profiles = dofile(assert(app.params.color_profile))

local function write_bytes(path, bytes)
  local file = assert(io.open(path, "wb"), "could not open GIF pixel evidence")
  local ok, failure = pcall(
    function() assert(file:write(bytes), "could not write GIF pixel evidence") end
  )
  local closed = file:close()
  if not ok then error(failure) end
  assert(closed, "could not close GIF pixel evidence")
end

local function copy_profile_state(state)
  local result = {}
  for key, value in pairs(state) do
    result[key] = value
  end
  return result
end

function module.encode(
  source,
  occurrences,
  composition_request,
  uuids,
  profile_state,
  output_path,
  evidence_directory
)
  assert(#occurrences > 0, "GIF requires at least one Frame occurrence")
  local previous = { sprite = app.activeSprite, layer = app.activeLayer, frame = app.activeFrame }
  local timeline, reopened = nil, nil
  local ok, result = pcall(function()
    local frames = {}
    for index, occurrence in ipairs(occurrences) do
      assert(occurrence.occurrence == index, "GIF occurrence order is inconsistent")
      assert(occurrence.source_duration_ms >= 10, "GIF Frame duration must be at least 10 ms")
      local image, paths, rejection, background = composition.render(
        source,
        occurrence.source_frame_number,
        composition_request,
        { x = 0, y = 0, width = source.width, height = source.height },
        selection,
        uuids,
        "rgb"
      )
      assert(image ~= nil, rejection and rejection.rejection.message or "GIF composition failed")
      if timeline == nil then
        timeline = Sprite(image.spec)
        assert(
          timeline.colorSpace == source.colorSpace,
          "GIF composition lost Source Color Profile"
        )
      else
        timeline:newEmptyFrame()
      end
      timeline:newCel(timeline.layers[1], index, image)
      timeline.frames[index].duration = occurrence.source_duration_ms / 1000
      frames[index] = {
        occurrence = index,
        source_frame_number = occurrence.source_frame_number,
        effective_background = background,
        resolved_layer_paths = paths,
      }
    end
    if profile_state.kind == "icc" then
      local private_state = copy_profile_state(profile_state)
      private_state.profile = timeline.colorSpace
      local converted = profiles.apply_live(
        timeline,
        "convert",
        { profile = { kind = "srgb" } },
        {},
        private_state
      )
      assert(converted.rejection == nil, "native GIF Color Profile conversion was rejected")
    else
      assert(
        profile_state.kind == "none" or profile_state.kind == "srgb",
        "unsupported GIF profile"
      )
    end
    for index = 1, #occurrences do
      local image = assert(timeline.layers[1]:cel(index), "GIF timeline Cel is absent").image
      assert(
        image.colorMode == ColorMode.RGB and image.bytesPerPixel == 4,
        "invalid GIF RGB evidence"
      )
      assert(image.rowStride == source.width * 4, "invalid GIF RGB row layout")
      write_bytes(evidence_directory .. "/" .. index .. ".pixels", image.bytes)
    end
    app.activeSprite, app.activeLayer, app.activeFrame =
      timeline, timeline.layers[1], timeline.frames[1]
    app.command.SaveFileCopyAs {
      ui = false,
      filename = output_path,
      ignoreEmpty = false,
      playSubtags = false,
      aniDir = "forward",
    }
    assert(app.fs.isFile(output_path), "native GIF encoding did not produce the staged file")
    reopened = assert(app.open(output_path), "could not reopen native GIF")
    assert(#reopened.frames == #occurrences, "encoded GIF occurrence count differs")
    assert(
      reopened.width == source.width and reopened.height == source.height,
      "encoded GIF Canvas differs"
    )
    for index = 1, #occurrences do
      local spec = reopened.spec
      spec.colorMode, spec.transparentColor = ColorMode.RGB, 0
      local decoded = Image(spec)
      decoded:drawSprite(reopened, index, 0, 0)
      assert(
        decoded.bytesPerPixel == 4 and decoded.rowStride == source.width * 4,
        "invalid GIF decoded layout"
      )
      write_bytes(evidence_directory .. "/" .. index .. ".gif-rgba", decoded.bytes)
    end
    return frames
  end)
  if reopened ~= nil then pcall(function() reopened:close() end) end
  if timeline ~= nil then pcall(function() timeline:close() end) end
  if previous.sprite ~= nil and previous.sprite.isValid then
    pcall(function() app.activeSprite = previous.sprite end)
    pcall(function() app.activeLayer = previous.layer end)
    pcall(function() app.activeFrame = previous.frame end)
  end
  if not ok then error(result) end
  return result
end

return module
