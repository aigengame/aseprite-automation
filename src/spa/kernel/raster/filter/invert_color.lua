-- Native Aseprite owns inversion and RGB Map quantization.
local module = {}
local application = dofile(app.params.filter_application)

local function validate_indexes(sprite, targets, basis, mask)
  local violations = {}
  for number, image in ipairs(targets.images) do
    local cel = image.layer:cel(image.frame)
    -- FilterManager crops the Cel to the Canvas with index-zero padding before
    -- visiting selected pixels. Transparent pixels are not skipped.
    for y = 0, sprite.height - 1 do
      for x = 0, sprite.width - 1 do
        if mask:contains(x, y) then
          local ix, iy = x - cel.position.x, y - cel.position.y
          local index = 0
          if ix >= 0 and iy >= 0 and ix < cel.image.width and iy < cel.image.height then
            index = cel.image:getPixel(ix, iy)
          end
          local inverted = 255 - index
          if index >= basis.palette_size or inverted >= basis.palette_size then
            local location
            for _, fact in ipairs(targets.existing_target_cels) do
              if fact.image_number == number and fact.frame_number == image.frame then
                location = fact
                break
              end
            end
            violations[#violations + 1] = {
              layer_path = assert(location).layer_path,
              frame_number = image.frame,
              canvas_position = { x = x, y = y },
              source_index = index,
              result_index = inverted,
            }
          end
        end
      end
    end
  end
  if #violations == 0 then return nil end
  local reason = "Source or inverted Index is outside the declared Effective Palette"
  return {
    rejection = {
      code = "filter_index_out_of_bounds",
      message = reason,
      details = { reason = reason, palette_basis = basis, index_violations = violations },
    },
  }
end

function module.apply(sprite, payload, uuids)
  local result = application.apply(
    sprite,
    payload,
    uuids,
    "Invert Color",
    function(flags)
      assert(app.command.InvertColor { ui = false, channels = flags }, "Native Invert Color failed")
      return true
    end,
    nil,
    function(targets, basis, mask)
      if payload.channels.kind == "index" then
        return validate_indexes(sprite, targets, basis, mask)
      end
    end
  )
  if not result.rejection then
    result.application = nil
    result.palette_indexes = nil
  end
  return result
end

return module
