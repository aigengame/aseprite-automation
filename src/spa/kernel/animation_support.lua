-- Exact declared audit and native full-canvas animation rendering.
local module = {}
local selection = dofile(assert(app.params.layer_select))
local inspection = dofile(assert(app.params.inspection))
local exporter = dofile(assert(app.params.export_image_support))

local function resolve(sprite, address, uuids)
  local selected, code, message = selection.resolve(sprite, address, uuids)
  if selected == nil then return nil, { rejection = { code = code, message = message, address = address } } end
  return selected, nil
end

local function visible(layer, sprite)
  local current = layer
  while current ~= sprite do
    if not current.isVisible or current.opacity == 0 then return false end
    current = current.parent
  end
  return true
end

local function regular_transparent(layer)
  return layer.isImage and layer.isTransparent and not layer.isGroup
    and not layer.isReference and not layer.isTilemap and not layer.isBackground
end

local function overlap_pixels(sprite, first, second, number)
  if not visible(first, sprite) or not visible(second, sprite) then return 0 end
  local left, right = first:cel(number), second:cel(number)
  if left == nil or right == nil or left.opacity == 0 or right.opacity == 0 then return 0 end
  local lx, ly = left.position.x, left.position.y
  local rx, ry = right.position.x, right.position.y
  local x0 = math.max(0, lx, rx)
  local y0 = math.max(0, ly, ry)
  local x1 = math.min(sprite.width, lx + left.image.width, rx + right.image.width)
  local y1 = math.min(sprite.height, ly + left.image.height, ry + right.image.height)
  local count = 0
  for y = y0, y1 - 1 do
    for x = x0, x1 - 1 do
      local alpha_left = app.pixelColor.rgbaA(left.image:getPixel(x - lx, y - ly))
      local alpha_right = app.pixelColor.rgbaA(right.image:getPixel(x - rx, y - ry))
      if alpha_left > 0 and alpha_right > 0 then count = count + 1 end
    end
  end
  return count
end

local function audit(payload)
  local sprite = assert(app.open(payload.sprite_file), "could not open Sprite File")
  local ok, result = pcall(function()
    assert(payload.from_frame >= 1 and payload.to_frame <= #sprite.frames, "Frame Range is outside Sprite")
    local uuids = inspection.saved_layer_uuids(sprite, payload.sprite_file)
    local required, durations, overlaps, findings = {}, {}, {}, {}
    for _, address in ipairs(payload.required_cels) do
      local selected, rejected = resolve(sprite, address.layer, uuids)
      if rejected then return rejected end
      local exists = selected.layer.isImage and selected.layer:cel(address.frame_number) ~= nil or false
      required[#required + 1] = {
        layer_path = selected.path, frame_number = address.frame_number, exists = exists,
      }
      if not exists then
        findings[#findings + 1] = {
          kind = "required_cel_missing", layer_path = selected.path, frame_number = address.frame_number,
        }
      end
    end
    if payload.duration_bounds ~= nil then
      for number = payload.from_frame, payload.to_frame do
        local duration = math.floor(sprite.frames[number].duration * 1000 + 0.5)
        durations[#durations + 1] = { frame_number = number, duration_ms = duration }
        if duration < payload.duration_bounds.minimum_ms or duration > payload.duration_bounds.maximum_ms then
          findings[#findings + 1] = {
            kind = "duration_out_of_bounds", frame_number = number, duration_ms = duration,
            minimum_ms = payload.duration_bounds.minimum_ms,
            maximum_ms = payload.duration_bounds.maximum_ms,
          }
        end
      end
    end
    if #payload.non_overlap > 0 then
      assert(sprite.colorMode == ColorMode.RGB, "non-overlap requires RGB Sprite")
    end
    for _, pair in ipairs(payload.non_overlap) do
      local first, first_rejected = resolve(sprite, pair.first_layer, uuids)
      if first_rejected then return first_rejected end
      local second, second_rejected = resolve(sprite, pair.second_layer, uuids)
      if second_rejected then return second_rejected end
      assert(regular_transparent(first.layer) and regular_transparent(second.layer),
        "non-overlap requires regular Transparent Layers")
      assert(first.layer ~= second.layer, "non-overlap requires distinct Layers")
      for number = payload.from_frame, payload.to_frame do
        local count = overlap_pixels(sprite, first.layer, second.layer, number)
        overlaps[#overlaps + 1] = {
          first_layer_path = first.path, second_layer_path = second.path,
          frame_number = number, overlap_pixels = count,
        }
        if count > 0 then
          findings[#findings + 1] = {
            kind = "layer_overlap", first_layer_path = first.path,
            second_layer_path = second.path, frame_number = number, overlap_pixels = count,
          }
        end
      end
    end
    return {
      complete = true, scope = { from_frame = payload.from_frame, to_frame = payload.to_frame },
      required_cels = required, durations = durations, overlaps = overlaps, findings = findings,
    }
  end)
  sprite:close()
  if not ok then error(result) end
  return result
end

local function alpha_bounds(bytes)
  local minimum, maximum = 255, 0
  for offset = 4, #bytes, 4 do
    local alpha = string.byte(bytes, offset)
    if alpha < minimum then minimum = alpha end
    if alpha > maximum then maximum = alpha end
  end
  return minimum, maximum
end

local function compare(payload)
  return exporter.with_source(payload.sprite_file,
    { payload.earlier_frame, payload.later_frame }, function(source)
      local earlier = exporter.render_frame(source, payload.earlier_frame).bytes
      local later = exporter.render_frame(source, payload.later_frame).bytes
      assert(#earlier == #later and #earlier == source.width * source.height * 4)
      local count = 0
      for offset = 1, #earlier, 4 do
        if earlier:sub(offset, offset + 3) ~= later:sub(offset, offset + 3) then
          count = count + 1
        end
      end
      return {
        earlier_frame = payload.earlier_frame, later_frame = payload.later_frame,
        color_mode = "rgb",
        bounds = { x = 0, y = 0, width = source.width, height = source.height },
        differing_pixels = count,
      }
    end)
end

local function preview(payload)
  return exporter.with_source(payload.source_sprite_file,
    { payload.earlier_frame, payload.later_frame }, function(source, profile)
      local earlier = exporter.render_frame(source, payload.earlier_frame)
      local later = exporter.render_frame(source, payload.later_frame)
      local disposable = Sprite(source.width, source.height, ColorMode.RGB)
      local ok, result = pcall(function()
        disposable:assignColorSpace(source.colorSpace)
        local lower = disposable.layers[1]
        lower.name = "later"
        disposable:newCel(lower, 1, later, Point(0, 0))
        local upper = disposable:newLayer()
        upper.name = "earlier"
        upper.blendMode = BlendMode.NORMAL
        upper.opacity = 128
        disposable:newCel(upper, 1, earlier, Point(0, 0))
        local rendered = exporter.render_frame(disposable, 1)
        local bytes = rendered.bytes
        local alpha_min, alpha_max = alpha_bounds(bytes)
        local file = assert(io.open(payload.staged_rgba_file, "wb"))
        assert(file:write(bytes))
        assert(file:close())
        assert(rendered:saveAs(payload.staged_png_file), "native PNG encoding failed")
        return {
          earlier_frame = payload.earlier_frame, later_frame = payload.later_frame,
          width = source.width, height = source.height, color_mode = "rgb",
          color_profile = profile, alpha_min = alpha_min, alpha_max = alpha_max,
          rendered_byte_size = #bytes, layer_order = { "later", "earlier" },
          earlier_blend_mode = "normal", earlier_opacity = 128,
        }
      end)
      disposable:close()
      if not ok then error(result) end
      return result
    end)
end

function module.execute(payload)
  if payload.operation == "audit" then return audit(payload) end
  if payload.operation == "compare" then return compare(payload) end
  if payload.operation == "preview" then return preview(payload) end
  error("unsupported Animation operation")
end

return module
