-- Resolve, replace, and persist one complete Cel-shared Image with a placement delta.
local module = {}
local inspection = dofile(app.params.inspection)
local persistence = dofile(app.params.persistence)
local selection = dofile(app.params.layer_select)
local cel = dofile(app.params.cel)
local digest = dofile(app.params.digest)
local all_sections = { "frames", "tags", "palettes", "layers", "cels", "slices", "tilesets" }

function module.reject(code, message) return { rejection = { code = code, message = message } } end

local function key(state) return table.concat(state.layer_path, "/") .. ":" .. state.frame_number end

function module.run(label, position_failure_code, edit)
  local open_sprite = nil
  local previous = { sprite = app.activeSprite, layer = app.activeLayer, frame = app.activeFrame }
  local function execute()
    local file = assert(io.open(app.params.request, "rb"))
    local request = json.decode(file:read("*a"))
    file:close()
    assert(request.kernel_protocol_version == 1, "unsupported Kernel Protocol")
    local payload = assert(request.payload)
    open_sprite = assert(app.open(payload.source_sprite_file), "could not open Source Sprite File")
    local uuids = inspection.saved_layer_uuids(open_sprite, payload.source_sprite_file)
    local layer, path, refused = cel.resolve(open_sprite, payload.target, selection, uuids)
    if refused then return refused end
    if not cel.is_regular_transparent(layer) then
      return module.reject(
        "cel_unsupported_target",
        label .. " requires a regular Transparent Layer"
      )
    end
    local target_cel = layer:cel(payload.target.frame_number)
    if target_cel == nil then return module.reject("cel_not_found", "Cel does not exist") end
    local source = target_cel.image
    local before = cel.affected(open_sprite, source)
    local before_by_key = {}
    for _, state in ipairs(before) do
      local selected = assert(selection.resolve(open_sprite, { layer_path = state.layer_path }, {}))
      if not cel.is_regular_transparent(selected.layer) then
        return module.reject("cel_unsupported_target", "Shared Image has a non-regular Cel")
      end
      before_by_key[key(state)] = state
    end
    local mode = ({
      [ColorMode.RGB] = "rgb",
      [ColorMode.GRAY] = "grayscale",
      [ColorMode.INDEXED] = "indexed",
    })[source.colorMode]
    assert(mode ~= nil, "unsupported Image Color Mode")
    local old_width, old_height = source.width, source.height
    local before_digest = digest.image_content(source, mode)
    local replacement, delta, facts = edit(payload, source, open_sprite, before)
    if replacement == nil then return delta end
    assert(
      digest.image_content(source, mode).value == before_digest.value,
      label .. " mutated source"
    )
    assert(replacement.colorMode == source.colorMode, label .. " changed Color Mode")
    assert(
      replacement.spec.transparentColor == source.spec.transparentColor,
      label .. " changed Image mask"
    )
    for _, state in ipairs(before) do
      local x, y = state.position.x + delta.x, state.position.y + delta.y
      if x < -32768 or x > 32767 or y < -32768 or y > 32767 then
        return module.reject(
          position_failure_code,
          "Position for Cel " .. key(state) .. " exceeds signed 16-bit bounds"
        )
      end
    end
    local expected_digest = digest.image_content(replacement, mode)
    local width, height = replacement.width, replacement.height
    app.transaction(label, function()
      target_cel.image = replacement
      for _, state in ipairs(before) do
        local selected =
          assert(selection.resolve(open_sprite, { layer_path = state.layer_path }, {}))
        selected.layer:cel(state.frame_number).position =
          Point(state.position.x + delta.x, state.position.y + delta.y)
      end
    end)
    local live_affected = cel.affected(open_sprite, target_cel.image)
    assert(#live_affected == #before, "Image mutation changed linked-Cel scope")
    for _, state in ipairs(live_affected) do
      assert(before_by_key[key(state)] ~= nil, "Image mutation changed Cel identity")
    end
    local live = persistence.snapshot(open_sprite, inspection, digest, all_sections, uuids)
    assert(open_sprite:saveAs(payload.staged_sprite_file), "could not save staged Sprite")
    open_sprite:close()
    open_sprite = assert(app.open(payload.staged_sprite_file), "could not reopen staged Sprite")
    local reopened_uuids = inspection.saved_layer_uuids(open_sprite, payload.staged_sprite_file)
    local reopened =
      persistence.snapshot(open_sprite, inspection, digest, all_sections, reopened_uuids)
    persistence.assert_same(live, reopened, label)
    local reopened_layer = assert(selection.resolve(open_sprite, { layer_path = path }, {})).layer
    local reopened_target = assert(reopened_layer:cel(payload.target.frame_number))
    local reopened_affected = cel.affected(open_sprite, reopened_target.image)
    assert(#reopened_affected == #before, "persisted linked-Cel scope changed")
    local changes = {}
    for _, state in ipairs(reopened_affected) do
      local prior = assert(before_by_key[key(state)], "persisted Cel identity changed")
      assert(
        state.position.x == prior.position.x + delta.x
          and state.position.y == prior.position.y + delta.y
      )
      assert(state.image_bounds.width == width and state.image_bounds.height == height)
      changes[#changes + 1] = {
        layer_path = state.layer_path,
        frame_number = state.frame_number,
        before_position = prior.position,
        after_position = state.position,
        before_image_bounds = { width = old_width, height = old_height },
        after_image_bounds = { width = width, height = height },
      }
    end
    local after_digest = digest.image_content(reopened_target.image, mode)
    assert(
      after_digest.value == expected_digest.value,
      "persisted Image differs from transformed pixels"
    )
    open_sprite:close()
    open_sprite = nil
    facts.target = { layer = { layer_path = path }, frame_number = payload.target.frame_number }
    facts.color_mode = mode
    facts.before_content_digest, facts.after_content_digest = before_digest, after_digest
    facts.affected_cels = changes
    facts.native_sharing_preserved = true
    facts.sprite = reopened.sprite
    facts.persisted_reopen_verified = true
    return facts
  end
  local ok, result = pcall(execute)
  if open_sprite ~= nil then pcall(function() open_sprite:close() end) end
  if previous.sprite ~= nil and previous.sprite.isValid then
    pcall(function() app.activeSprite = previous.sprite end)
    pcall(function() app.activeLayer = previous.layer end)
    pcall(function() app.activeFrame = previous.frame end)
  end
  local response = ok and { kernel_protocol_version = 1, status = "ok", result = result }
    or {
      kernel_protocol_version = 1,
      status = "error",
      cause = "operation_rejected",
      message = tostring(result),
    }
  local file = assert(io.open(app.params.response, "wb"))
  file:write(json.encode(response))
  file:close()
end

return module
