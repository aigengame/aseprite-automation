-- Fixed packaged Operation Plan handler. Request files contain data only.
local kernel_protocol_version = 1
local inspection = dofile(app.params.inspection)
local creation = dofile(app.params.creation)
local paint = dofile(app.params.paint)
local digest = dofile(app.params.digest)
local capability_probe = dofile(app.params.capability_probe)
local all_sections = {
  "frames",
  "tags",
  "palettes",
  "layers",
  "cels",
  "slices",
  "tilesets",
}
local open_sprite = nil
local verified_uuids = {}
local failed_step = nil
local failed_operation = nil
local runtime_incompatibility = nil
local previous_editor_state = {
  sprite = app.activeSprite,
  layer = app.activeLayer,
  frame = app.activeFrame,
  background_color = app.bgColor,
}

local function restore_editor_state()
  pcall(function() app.bgColor = previous_editor_state.background_color end)
  local previous = previous_editor_state.sprite
  if previous ~= nil and previous.isValid then
    pcall(function() app.activeSprite = previous end)
    pcall(function() app.activeLayer = previous_editor_state.layer end)
    pcall(function() app.activeFrame = previous_editor_state.frame end)
  end
end

local function verify_runtime(requirements)
  local observed = capability_probe.observe()
  local available = {}
  for _, capability in ipairs(observed) do
    available[capability] = true
  end
  local missing = {}
  for _, capability in ipairs(requirements.required_capabilities) do
    if not available[capability] then missing[#missing + 1] = capability end
  end
  if
    _VERSION ~= requirements.lua_language
    or app.apiVersion < requirements.minimum_api_version
    or #missing > 0
  then
    runtime_incompatibility = {
      aseprite_version = tostring(app.version),
      lua_version = _VERSION,
      api_version = app.apiVersion,
      required_lua_language = requirements.lua_language,
      minimum_api_version = requirements.minimum_api_version,
      missing_capabilities = missing,
    }
    error("Plan runtime does not meet the selected Step requirements")
  end
end

local function difference(left, right, at)
  if type(left) ~= type(right) then
    if tonumber(left) ~= nil and tonumber(left) == tonumber(right) then return nil end
    return at .. " (" .. type(left) .. " / " .. type(right) .. ")"
  end
  if type(left) ~= "table" then
    if left == right then return nil end
    return at
      .. " ("
      .. type(left)
      .. ":"
      .. tostring(left)
      .. " / "
      .. type(right)
      .. ":"
      .. tostring(right)
      .. ")"
  end
  for key, value in pairs(left) do
    local found = difference(value, right[key], at .. "." .. tostring(key))
    if found ~= nil then return found end
  end
  for key, _ in pairs(right) do
    if left[key] == nil then return at .. "." .. tostring(key) end
  end
  return nil
end

local function document_facts(sprite)
  local images = {}
  for _, cel in ipairs(sprite.cels) do
    local image = cel.image
    images[#images + 1] = {
      width = image.width,
      height = image.height,
      bytes_per_pixel = image.bytesPerPixel,
      row_stride = image.rowStride,
      content = digest.fnv1a64(image.bytes),
    }
  end
  return { sprite = inspection.inspect(sprite, all_sections, verified_uuids), images = images }
end

local function verify_postconditions(sprite, conditions)
  if conditions.width ~= nil then
    assert(sprite.width == conditions.width, "Plan width Postcondition failed")
  end
  if conditions.height ~= nil then
    assert(sprite.height == conditions.height, "Plan height Postcondition failed")
  end
  if conditions.frame_count ~= nil then
    assert(#sprite.frames == conditions.frame_count, "Plan frame_count Postcondition failed")
  end
  if conditions.color_mode ~= nil then
    local actual = sprite.colorMode == ColorMode.RGB and "rgb"
      or sprite.colorMode == ColorMode.GRAY and "grayscale"
      or sprite.colorMode == ColorMode.INDEXED and "indexed"
      or "unknown"
    assert(actual == conditions.color_mode, "Plan color_mode Postcondition failed")
  end
end

local function execute_step(step)
  local input = assert(step.input, "Plan Step has no input")
  if step.operation == "sprite create" then
    assert(open_sprite == nil, "Sprite creation must be the first Step")
    open_sprite = creation.create_live(input)
    verified_uuids = {}
    return {
      sprite = inspection.inspect(open_sprite, all_sections, verified_uuids),
      initial_layer = creation.verify_persisted_initial_layer(open_sprite, input.initial_layer),
    }
  end
  assert(open_sprite ~= nil, "Plan has no active Sprite")
  if step.operation == "sprite get" then
    return { sprite = inspection.inspect(open_sprite, input.inspection_scope, verified_uuids) }
  end
  if step.operation == "paint apply" then
    local evidence = paint.apply_live(open_sprite, input, digest)
    return evidence
  end
  error("Operation is not Plan-eligible")
end

local function execute()
  local request_file = assert(io.open(app.params.request, "rb"))
  local request = json.decode(request_file:read("*a"))
  request_file:close()
  assert(
    request.kernel_protocol_version == kernel_protocol_version,
    "unsupported Kernel Protocol version"
  )
  local payload = assert(request.payload)
  local requirements = assert(payload.runtime_requirements)
  verify_runtime(requirements)
  assert(payload.steps ~= nil and #payload.steps > 0, "Plan has no Steps")
  if type(payload.source_sprite_file) == "string" then
    open_sprite = assert(app.open(payload.source_sprite_file), "could not open Source Sprite File")
    verified_uuids = inspection.saved_layer_uuids(open_sprite, payload.source_sprite_file)
  end
  local outcomes = {}
  for index, step in ipairs(payload.steps) do
    failed_step = index
    failed_operation = step.operation
    local result = execute_step(step)
    outcomes[#outcomes + 1] = { operation = step.operation, result = result }
    failed_step = nil
    failed_operation = nil
  end
  assert(open_sprite ~= nil, "Plan has no Sprite")
  local conditions = assert(payload.postconditions)
  verify_postconditions(open_sprite, conditions)
  local before = document_facts(open_sprite)
  local persisted = false
  if type(payload.staged_sprite_file) == "string" then
    assert(open_sprite:saveAs(payload.staged_sprite_file), "could not save staged Sprite")
    open_sprite:close()
    open_sprite = nil
    open_sprite = assert(app.open(payload.staged_sprite_file), "could not reopen staged Sprite")
    verified_uuids = inspection.saved_layer_uuids(open_sprite, payload.staged_sprite_file)
    local after = document_facts(open_sprite)
    local persisted_palettes = after.sprite.palettes
    if before.sprite.metadata.color_mode ~= "indexed" then
      -- RGB/Grayscale palette entries are not image semantics; Aseprite may
      -- normalize their alpha when it serializes the document.
      before.sprite.palettes = nil
      after.sprite.palettes = nil
    end
    local inspection_mismatch = difference(before.sprite, after.sprite, "sprite")
    assert(
      inspection_mismatch == nil,
      "persisted Plan inspection differs at " .. tostring(inspection_mismatch)
    )
    local image_mismatch = difference(before.images, after.images, "images")
    assert(image_mismatch == nil, "persisted Plan images differ at " .. tostring(image_mismatch))
    after.sprite.palettes = persisted_palettes
    verify_postconditions(open_sprite, conditions)
    persisted = true
    before = after
  end
  local response = {
    steps = outcomes,
    final_sprite = before.sprite,
    persisted_reopen_verified = persisted,
  }
  open_sprite:close()
  open_sprite = nil
  return response
end

local ok, result = pcall(execute)
local response
if ok then
  response = {
    kernel_protocol_version = kernel_protocol_version,
    status = "ok",
    result = result,
  }
else
  if open_sprite ~= nil then pcall(function() open_sprite:close() end) end
  response = {
    kernel_protocol_version = kernel_protocol_version,
    status = "error",
    cause = runtime_incompatibility and "runtime_incompatible" or "operation_rejected",
    message = tostring(result),
    failed_step = failed_step,
    failed_operation = failed_operation,
    runtime_compatibility = runtime_incompatibility,
  }
end
restore_editor_state()
local response_file = assert(io.open(app.params.response, "wb"))
response_file:write(json.encode(response))
response_file:close()
