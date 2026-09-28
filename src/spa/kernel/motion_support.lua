-- One native motion owner for standalone and Plan execution.
local module = {}
local cel = dofile(app.params.cel)
local selection = dofile(app.params.layer_select)
local rounding = dofile(app.params.rounding)
local inspection = dofile(app.params.inspection)
local persistence = dofile(app.params.persistence)
local digest = dofile(app.params.digest)
local sections = { "frames", "tags", "palettes", "layers", "cels", "slices", "tilesets" }
local json_null = json.decode("null")

local function reject(code, message, number)
  return { rejection = { code = code, message = message, frame_number = number } }
end

-- Divide factor*numerator exactly without constructing their overflowing product.
-- Residues stay below 2*denominator. Smoothstep's denominator fits for a native
-- file timeline (WORD Frame count) plus the bounded Plan's single-Frame additions.
local function multiply_fraction(factor, numerator, denominator)
  local whole, remainder = 0, 0
  local add_whole, add_remainder = numerator // denominator, numerator % denominator
  while factor > 0 do
    if factor % 2 == 1 then
      remainder = remainder + add_remainder
      whole = whole + add_whole + remainder // denominator
      remainder = remainder % denominator
    end
    factor = factor // 2
    local doubled = 2 * add_remainder
    add_whole = 2 * add_whole + doubled // denominator
    add_remainder = doubled % denominator
  end
  return whole, remainder
end

local function interpolate(left, right, numerator, denominator, policy)
  left, right = assert(math.tointeger(left)), assert(math.tointeger(right))
  local delta = right - left
  local whole, remainder = multiply_fraction(math.abs(delta), numerator, denominator)
  if delta < 0 then
    whole, remainder = -whole, -remainder
  end
  whole = left + whole
  if remainder < 0 then
    whole, remainder = whole - 1, remainder + denominator
  end
  return rounding.parts(whole, remainder, denominator, policy)
end

local function sample(curve, number, index)
  while index < #curve.keys and curve.keys[index + 1].frame_number <= number do
    index = index + 1
  end
  local left = curve.keys[index]
  local right = curve.keys[index + 1] or left
  local numerator, denominator = 0, 1
  if number ~= left.frame_number and curve.interpolation ~= "step" then
    local n = number - assert(math.tointeger(left.frame_number))
    local d = assert(math.tointeger(right.frame_number - left.frame_number))
    if curve.interpolation == "linear" then
      numerator, denominator = n, d
    else
      assert(curve.interpolation == "smoothstep")
      numerator, denominator = n * n * (3 * d - 2 * n), d * d * d
    end
  end
  if left.offset then
    return {
      x = interpolate(left.offset.x, right.offset.x, numerator, denominator, curve.rounding),
      y = interpolate(left.offset.y, right.offset.y, numerator, denominator, curve.rounding),
    },
      index
  end
  return interpolate(left.opacity, right.opacity, numerator, denominator, curve.rounding), index
end

function module.apply_live(sprite, input, uuids)
  local layer, path, refused =
    cel.resolve(sprite, { layer = input.layer, frame_number = input.from_frame }, selection, uuids)
  if refused then return refused end
  if input.to_frame > #sprite.frames then
    return reject("cel_frame_out_of_bounds", "Frame Range is outside the Sprite timeline")
  end
  if not cel.is_regular_transparent(layer) then
    return reject("cel_unsupported_target", "Motion requires a regular Transparent Layer")
  end
  local changes, targets = {}, {}
  local position_index, opacity_index = 1, 1
  for number = math.tointeger(input.from_frame), math.tointeger(input.to_frame) do
    local target = layer:cel(number)
    if target == nil then return reject("cel_not_found", "Motion Cel does not exist", number) end
    local before = cel.inspect(sprite, layer, path, number)
    if #before.linked_cels > 0 then
      return reject("motion_linked_cel", "Motion requires an explicitly unlinked Cel", number)
    end
    local offset, opacity = nil, before.opacity
    if input.position_offsets then
      offset, position_index = sample(input.position_offsets, number, position_index)
    end
    if input.opacity then
      opacity, opacity_index = sample(input.opacity, number, opacity_index)
    end
    local x = before.position.x + (offset and offset.x or 0)
    local y = before.position.y + (offset and offset.y or 0)
    if x < -32768 or x > 32767 or y < -32768 or y > 32767 then
      return reject(
        "motion_position_out_of_bounds",
        "Motion exceeds signed 16-bit coordinates",
        number
      )
    end
    assert(opacity >= 0 and opacity <= 255)
    targets[#targets + 1] = { cel = target, x = x, y = y, opacity = opacity }
    changes[#changes + 1] = { before = before, offset = offset or json_null }
  end
  local before_count = #sprite.cels
  local expected = persistence.snapshot(sprite, inspection, digest, sections, uuids)
  local target_by_frame = {}
  for _, target in ipairs(targets) do
    target_by_frame[target.cel.frameNumber] = target
  end
  for _, fact in ipairs(expected.sprite.cels) do
    local target = target_by_frame[fact.frame_number]
    if target and table.concat(fact.layer_path, "/") == table.concat(path, "/") then
      fact.bounds.x, fact.bounds.y, fact.opacity = target.x, target.y, target.opacity
    end
  end
  app.transaction("Apply Cel motion", function()
    for _, target in ipairs(targets) do
      target.cel.position = Point(target.x, target.y)
      target.cel.opacity = target.opacity
    end
  end)
  local actual = persistence.snapshot(sprite, inspection, digest, sections, uuids)
  persistence.assert_equal(expected, actual, "Motion preserved document facts")
  for index, target in ipairs(targets) do
    changes[index].after = cel.inspect(sprite, layer, path, target.cel.frameNumber)
  end
  return { before_cel_count = before_count, cels = changes, unchanged_facts_verified = true }
end

return module
