-- Fixed Cel-targeted whole-Image orientation and native persistence verification.
local inspection = dofile(app.params.inspection)
local selection = dofile(app.params.layer_select)
local cel = dofile(app.params.cel)
local persistence = dofile(app.params.persistence)
local digest = dofile(app.params.digest)
local transform = dofile(app.params.image_orientation_transform)
local sections = { "frames", "tags", "palettes", "layers", "cels", "slices", "tilesets" }
local open_sprite = nil
local previous = { sprite = app.activeSprite, layer = app.activeLayer, frame = app.activeFrame }

local function reject(code, message) return { rejection = { code = code, message = message } } end

local function key(state) return table.concat(state.layer_path, "/") .. ":" .. state.frame_number end

local function accepts(layer, operation)
  if operation == "rotate" then return cel.is_regular_transparent(layer) end
  return layer.isImage and not layer.isTilemap and not layer.isGroup
end

local function execute()
  local file = assert(io.open(app.params.request, "rb"))
  local request = json.decode(file:read("*a"))
  file:close()
  assert(request.kernel_protocol_version == 1, "unsupported Kernel Protocol")
  local payload = assert(request.payload)
  local operation = payload.operation
  assert(operation == "flip" or operation == "rotate", "unsupported Image orientation operation")
  open_sprite = assert(app.open(payload.source_sprite_file), "could not open Source Sprite File")
  local uuids = inspection.saved_layer_uuids(open_sprite, payload.source_sprite_file)
  local layer, path, refused = cel.resolve(open_sprite, payload.target, selection, uuids)
  if refused then return refused end
  if not accepts(layer, operation) then
    return reject("cel_unsupported_target", "Unsupported Image target")
  end
  local target = layer:cel(payload.target.frame_number)
  if target == nil then return reject("cel_not_found", "Cel does not exist") end
  local image = target.image
  if image.colorMode == ColorMode.TILEMAP then
    return reject("cel_unsupported_target", "Tilemap Images are not supported")
  end
  local before = cel.affected(open_sprite, image)
  local before_by_key = {}
  for _, state in ipairs(before) do
    local selected = assert(selection.resolve(open_sprite, { layer_path = state.layer_path }, {}))
    if not accepts(selected.layer, operation) then
      return reject("cel_unsupported_target", "Shared Image includes an unsupported Cel")
    end
    before_by_key[key(state)] = state
  end
  local mode = assert(
    ({
      [ColorMode.RGB] = "rgb",
      [ColorMode.GRAY] = "grayscale",
      [ColorMode.INDEXED] = "indexed",
    })[image.colorMode],
    "unsupported Image Color Mode"
  )
  local old_width, old_height = image.width, image.height
  local new_width, new_height = old_width, old_height
  if operation == "rotate" and payload.angle ~= 180 then
    new_width, new_height = old_height, old_width
  end
  local dx, dy = 0, 0
  local policy = nil
  if operation == "rotate" then
    local requested = assert(payload.position_policy)
    if requested.kind == "keep" then
      policy = { kind = "keep" }
    else
      assert(requested.kind == "pivot", "unsupported Cel Position Policy")
      local x, y = transform.rotated_point(
        requested.pivot_x,
        requested.pivot_y,
        old_width,
        old_height,
        payload.angle
      )
      dx, dy = requested.pivot_x - x, requested.pivot_y - y
      policy = { kind = "pivot", pivot_x = requested.pivot_x, pivot_y = requested.pivot_y }
    end
    for _, state in ipairs(before) do
      local x, y = state.position.x + dx, state.position.y + dy
      if x < -32768 or x > 32767 or y < -32768 or y > 32767 then
        return reject(
          "image_rotate_position_out_of_bounds",
          "Resulting Cel position cannot be persisted"
        )
      end
    end
  end
  local old_spec = image.spec
  local before_digest = digest.image_content(image, mode)
  local original = persistence.snapshot(open_sprite, inspection, digest, sections, uuids)
  local before_bounds = {}
  for _, state in ipairs(original.sprite.cels) do
    before_bounds[key(state)] = state.bounds
  end
  app.transaction(operation .. " Image", function()
    if operation == "flip" then
      transform.flip(image, payload.axis)
    else
      target.image = transform.rotate(image, payload.angle)
      for _, state in ipairs(before) do
        local selected =
          assert(selection.resolve(open_sprite, { layer_path = state.layer_path }, {}))
        selected.layer:cel(state.frame_number).position =
          Point(state.position.x + dx, state.position.y + dy)
      end
    end
  end)
  image = target.image
  assert(
    image.width == new_width and image.height == new_height,
    "Image transform changed dimensions"
  )
  assert(image.colorMode == old_spec.colorMode, "Image Color Mode changed")
  assert(image.spec.transparentColor == old_spec.transparentColor, "Image mask changed")
  local live_affected = cel.affected(open_sprite, target.image)
  assert(#live_affected == #before, "Image transform changed linked-Cel scope")
  for _, state in ipairs(live_affected) do
    local prior = assert(before_by_key[key(state)], "Image transform changed Cel identity")
    assert(state.position.x == prior.position.x + dx and state.position.y == prior.position.y + dy)
  end
  local live = persistence.snapshot(open_sprite, inspection, digest, sections, uuids)
  -- Permit only the declared Image replacement and (for rotation) Cel bounds.
  -- Both snapshots enumerate native sprite.cels in the same order.
  for index, state in ipairs(live.sprite.cels) do
    if before_by_key[key(state)] ~= nil then
      original.images[index] = live.images[index]
      if operation == "rotate" then
        original.sprite.cels[index].bounds = live.sprite.cels[index].bounds
      end
    end
  end
  persistence.assert_equal(original, live, "Image " .. operation .. " invariants")
  assert(open_sprite:saveAs(payload.staged_sprite_file), "could not save staged Sprite")
  open_sprite:close()
  open_sprite = assert(app.open(payload.staged_sprite_file), "could not reopen staged Sprite")
  local reopened_uuids = inspection.saved_layer_uuids(open_sprite, payload.staged_sprite_file)
  local reopened = persistence.snapshot(open_sprite, inspection, digest, sections, reopened_uuids)
  persistence.assert_same(live, reopened, "Image " .. operation)
  local reopened_layer = assert(selection.resolve(open_sprite, { layer_path = path }, {})).layer
  local reopened_target = assert(reopened_layer:cel(payload.target.frame_number))
  local after = cel.affected(open_sprite, reopened_target.image)
  assert(#after == #before, "Persisted linked-Cel scope changed")
  local bounds_by_key = {}
  for _, state in ipairs(reopened.sprite.cels) do
    bounds_by_key[key(state)] = state.bounds
  end
  local effects = {}
  for _, state in ipairs(after) do
    local address = key(state)
    effects[#effects + 1] = {
      before = assert(before_by_key[address], "Persisted Cel identity changed"),
      after = state,
      before_bounds = before_bounds[address],
      after_bounds = bounds_by_key[address],
    }
  end
  local after_digest = digest.image_content(reopened_target.image, mode)
  open_sprite:close()
  open_sprite = nil
  return {
    target = { layer = { layer_path = path }, frame_number = payload.target.frame_number },
    image_coordinate_space = "image-pixel",
    cel_coordinate_space = "canvas-pixel",
    old_size = { width = old_width, height = old_height },
    new_size = { width = new_width, height = new_height },
    position_delta = { x = dx, y = dy },
    axis = payload.axis,
    angle = payload.angle,
    position_policy = policy,
    color_mode = mode,
    before_content_digest = before_digest,
    after_content_digest = after_digest,
    affected_cels = effects,
    native_sharing_preserved = true,
    unchanged_native_invariants = {
      sprite_structure = true,
      unrelated_cels = true,
      cel_opacity_and_z_index = true,
      color_mode = true,
    },
    sprite = reopened.sprite,
    persisted_reopen_verified = true,
  }
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
local response_file = assert(io.open(app.params.response, "wb"))
response_file:write(json.encode(response))
response_file:close()
