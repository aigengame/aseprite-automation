-- Cel-targeted scaling policy over the shared Image mutation lifecycle.
local mutation = dofile(app.params.image_cel_mutation)
local transform = dofile(app.params.image_resize_transform)
local rounding = dofile(app.params.rounding)
local json_null = json.decode("null")

local function rounded_offset(pivot, old_size, new_size, policy)
  local numerator = pivot * (old_size - new_size)
  local denominator = old_size
  local applied = rounding.ratio(numerator, denominator, policy)
  return { numerator = numerator, denominator = denominator, applied = applied }
end

local function offsets(policy, old_width, old_height, new_width, new_height)
  if policy.kind == "keep" then
    return { numerator = 0, denominator = 1, applied = 0 }, {
      numerator = 0,
      denominator = 1,
      applied = 0,
    }
  end
  assert(policy.kind == "pivot", "unsupported Cel Position Policy")
  return rounded_offset(policy.pivot_x, old_width, new_width, policy.rounding),
    rounded_offset(policy.pivot_y, old_height, new_height, policy.rounding)
end

mutation.run(
  "Image Resize",
  "image_resize_position_out_of_bounds",
  function(payload, source, sprite)
    local indexed_bilinear = source.colorMode == ColorMode.INDEXED and payload.method == "bilinear"
    local palette_number = payload.palette_frame_number
    if indexed_bilinear then
      if palette_number == nil or palette_number > #sprite.frames then
        return nil,
          mutation.reject(
            "image_resize_palette_basis_invalid",
            "Indexed bilinear requires an existing palette_frame_number"
          )
      end
    elseif palette_number ~= nil then
      return nil,
        mutation.reject(
          "image_resize_palette_basis_invalid",
          "palette_frame_number is not applicable"
        )
    end
    local old_width, old_height = source.width, source.height
    local offset_x, offset_y =
      offsets(payload.position_policy, old_width, old_height, payload.width, payload.height)
    local resized, palette_basis = transform.resize(
      source,
      sprite,
      payload.width,
      payload.height,
      payload.method,
      palette_number
    )
    return resized,
      { x = offset_x.applied, y = offset_y.applied },
      {
        old_size = { width = old_width, height = old_height },
        requested_size = { width = payload.width, height = payload.height },
        effective_size = { width = payload.width, height = payload.height },
        method = payload.method,
        position_policy = payload.position_policy.kind == "keep" and { kind = "keep" } or {
          kind = "pivot",
          pivot_x = payload.position_policy.pivot_x,
          pivot_y = payload.position_policy.pivot_y,
          rounding = payload.position_policy.rounding,
        },
        offset_x = offset_x,
        offset_y = offset_y,
        effective_palette = palette_basis or json_null,
      }
  end
)
