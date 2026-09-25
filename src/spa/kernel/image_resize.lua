-- Fixed Cel-targeted Image Resize handler. Runtime files carry data only.
local kernel_protocol_version = 1
local inspection = dofile(app.params.inspection)
local persistence = dofile(app.params.persistence)
local selection = dofile(app.params.layer_select)
local cel = dofile(app.params.cel)
local digest = dofile(app.params.digest)
local transform = dofile(app.params.image_resize_transform)
local all_sections = { "frames", "tags", "palettes", "layers", "cels", "slices", "tilesets" }
local json_null = json.decode("null")
local open_sprite = nil
local previous = { sprite = app.activeSprite, layer = app.activeLayer, frame = app.activeFrame }

local function reject(code, message)
  return { rejection = { code = code, message = message } }
end

local function key(state)
  return table.concat(state.layer_path, "/") .. ":" .. state.frame_number
end

local function rounded_offset(pivot, old_size, new_size, rounding)
  local numerator = pivot * (old_size - new_size)
  local denominator = old_size
  local applied
  if rounding == "floor" then
    applied = numerator // denominator
  elseif rounding == "ceil" then
    applied = -((-numerator) // denominator)
  elseif rounding == "toward-zero" then
    applied = numerator < 0 and -((-numerator) // denominator) or numerator // denominator
  elseif rounding == "nearest-away-from-zero" then
    local magnitude = (2 * math.abs(numerator) + denominator) // (2 * denominator)
    applied = numerator < 0 and -magnitude or magnitude
  else
    error("unsupported Cel Position rounding")
  end
  return { numerator = numerator, denominator = denominator, applied = applied }
end

local function offsets(policy, old_width, old_height, new_width, new_height)
  if policy.kind == "keep" then
    return { numerator = 0, denominator = 1, applied = 0 },
      { numerator = 0, denominator = 1, applied = 0 }
  end
  assert(policy.kind == "pivot", "unsupported Cel Position Policy")
  return rounded_offset(policy.pivot_x, old_width, new_width, policy.rounding),
    rounded_offset(policy.pivot_y, old_height, new_height, policy.rounding)
end

local function image_digest(image, color_mode)
  local header = table.concat({
    color_mode,
    ":",
    image.width,
    "x",
    image.height,
    ":",
    image.bytesPerPixel,
    ":",
    image.rowStride,
    ":",
  })
  return { algorithm = "fnv1a64", value = digest.fnv1a64(header, image.bytes) }
end

local function execute()
  local file = assert(io.open(app.params.request, "rb"))
  local request = json.decode(file:read("*a"))
  file:close()
  assert(request.kernel_protocol_version == kernel_protocol_version, "unsupported Kernel Protocol")
  local payload = assert(request.payload)
  open_sprite = assert(app.open(payload.source_sprite_file), "could not open Source Sprite File")
  local uuids = inspection.saved_layer_uuids(open_sprite, payload.source_sprite_file)
  local layer, path, refused = cel.resolve(open_sprite, payload.target, selection, uuids)
  if refused then return refused end
  if not cel.is_regular_transparent(layer) then
    return reject("cel_unsupported_target", "Image Resize requires a regular Transparent Layer")
  end
  local target_cel = layer:cel(payload.target.frame_number)
  if target_cel == nil then return reject("cel_not_found", "Cel does not exist") end
  local source_image = target_cel.image
  local before = cel.affected(open_sprite, source_image)
  for _, state in ipairs(before) do
    local selected = assert(selection.resolve(open_sprite, { layer_path = state.layer_path }, {}))
    if not cel.is_regular_transparent(selected.layer) then
      return reject("cel_unsupported_target", "Shared Image has a non-regular Cel")
    end
  end
  local mode = ({ [ColorMode.RGB] = "rgb", [ColorMode.GRAY] = "grayscale", [ColorMode.INDEXED] = "indexed" })[source_image.colorMode]
  assert(mode ~= nil, "unsupported Image Color Mode")
  local palette_number = payload.palette_frame_number
  if mode == "indexed" and payload.method == "bilinear" then
    if palette_number == nil or palette_number > #open_sprite.frames then
      return reject("image_resize_palette_basis_invalid", "Indexed bilinear requires an existing palette_frame_number")
    end
  elseif palette_number ~= nil then
    return reject("image_resize_palette_basis_invalid", "palette_frame_number is not applicable")
  end
  local old_width, old_height = source_image.width, source_image.height
  local offset_x, offset_y = offsets(
    payload.position_policy, old_width, old_height, payload.width, payload.height
  )
  for _, state in ipairs(before) do
    local x = state.position.x + offset_x.applied
    local y = state.position.y + offset_y.applied
    if x < -32768 or x > 32767 or y < -32768 or y > 32767 then
      return reject(
        "image_resize_position_out_of_bounds",
        "Resized position for Cel " .. key(state) .. " exceeds signed 16-bit bounds"
      )
    end
  end
  local before_digest = image_digest(source_image, mode)
  app.activeSprite = open_sprite
  app.activeLayer = layer
  local resized, palette_basis = transform.resize(
    source_image,
    open_sprite,
    payload.width,
    payload.height,
    payload.method,
    palette_number
  )
  assert(image_digest(source_image, mode).value == before_digest.value, "Image Resize mutated source")
  app.transaction("Resize Image", function()
    target_cel.image = resized
    for _, state in ipairs(before) do
      local selected = assert(selection.resolve(open_sprite, { layer_path = state.layer_path }, {}))
      local affected = assert(selected.layer:cel(state.frame_number))
      affected.position = Point(
        state.position.x + offset_x.applied,
        state.position.y + offset_y.applied
      )
    end
  end)
  local live_affected = cel.affected(open_sprite, target_cel.image)
  assert(#live_affected == #before, "Image Resize changed linked-Cel scope")
  local before_by_key = {}
  for _, state in ipairs(before) do before_by_key[key(state)] = state end
  for _, state in ipairs(live_affected) do
    assert(before_by_key[key(state)] ~= nil, "Image Resize changed Cel identity")
  end
  local live = persistence.snapshot(open_sprite, inspection, digest, all_sections, uuids)
  assert(open_sprite:saveAs(payload.staged_sprite_file), "could not save staged Sprite")
  open_sprite:close()
  open_sprite = assert(app.open(payload.staged_sprite_file), "could not reopen staged Sprite")
  local reopened_uuids = inspection.saved_layer_uuids(open_sprite, payload.staged_sprite_file)
  local reopened = persistence.snapshot(
    open_sprite, inspection, digest, all_sections, reopened_uuids
  )
  persistence.assert_same(live, reopened, "Image Resize")
  local reopened_layer = assert(selection.resolve(open_sprite, { layer_path = path }, {})).layer
  local reopened_target = assert(reopened_layer:cel(payload.target.frame_number))
  local reopened_affected = cel.affected(open_sprite, reopened_target.image)
  assert(#reopened_affected == #before, "persisted linked-Cel scope changed")
  local changes = {}
  for _, state in ipairs(reopened_affected) do
    local prior = assert(before_by_key[key(state)], "persisted Cel identity changed")
    assert(state.position.x == prior.position.x + offset_x.applied)
    assert(state.position.y == prior.position.y + offset_y.applied)
    assert(state.image_bounds.width == payload.width and state.image_bounds.height == payload.height)
    changes[#changes + 1] = {
      layer_path = state.layer_path,
      frame_number = state.frame_number,
      before_position = prior.position,
      after_position = state.position,
      before_image_bounds = { width = old_width, height = old_height },
      after_image_bounds = { width = payload.width, height = payload.height },
    }
  end
  local after_digest = image_digest(reopened_target.image, mode)
  open_sprite:close()
  open_sprite = nil
  return {
    target = { layer = { layer_path = path }, frame_number = payload.target.frame_number },
    old_size = { width = old_width, height = old_height },
    requested_size = { width = payload.width, height = payload.height },
    effective_size = { width = payload.width, height = payload.height },
    method = payload.method,
    -- Encode a fresh result table; reusing the decoded request table serializes as null.
    position_policy = payload.position_policy.kind == "keep"
        and { kind = "keep" }
      or {
        kind = "pivot",
        pivot_x = payload.position_policy.pivot_x,
        pivot_y = payload.position_policy.pivot_y,
        rounding = payload.position_policy.rounding,
      },
    offset_x = offset_x,
    offset_y = offset_y,
    color_mode = mode,
    effective_palette = palette_basis or json_null,
    before_content_digest = before_digest,
    after_content_digest = after_digest,
    affected_cels = changes,
    native_sharing_preserved = true,
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
local response
if ok then
  response = { kernel_protocol_version = kernel_protocol_version, status = "ok", result = result }
else
  response = {
    kernel_protocol_version = kernel_protocol_version,
    status = "error",
    cause = "operation_rejected",
    message = tostring(result),
  }
end
local response_file = assert(io.open(app.params.response, "wb"))
response_file:write(json.encode(response))
response_file:close()
