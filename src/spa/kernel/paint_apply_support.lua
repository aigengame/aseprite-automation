-- Paint-owned exact Pixel Patch semantics shared by the handler and capability probe.
local module = {}
local colors = dofile(app.params.raster_color)
local max_patch_pixels = 256

local function copy_run(run)
  return { x = run.x, y = run.y, length = run.length, color = colors.copy_color(run.color) }
end

local function copy_rectangle(rectangle)
  return {
    x = rectangle.x,
    y = rectangle.y,
    width = rectangle.width,
    height = rectangle.height,
  }
end

local function copy_address(address)
  local path = {}
  for _, index in ipairs(address.layer_path) do
    path[#path + 1] = index
  end
  return { layer_path = path, frame_number = address.frame_number }
end

local function copy_selection(selection)
  if selection == nil then return nil end
  if selection.kind == "empty" then return { kind = "empty" } end
  if selection.kind == "all" then
    return { kind = "all", rectangle = copy_rectangle(selection.rectangle) }
  end
  local rows = {}
  for _, row in ipairs(selection.rows) do
    local runs = {}
    for _, run in ipairs(row.runs) do
      runs[#runs + 1] = { x = run.x, length = run.length }
    end
    rows[#rows + 1] = { y = row.y, runs = runs }
  end
  return { kind = "mask", bounds = copy_rectangle(selection.bounds), rows = rows }
end

local function point(point_value) return { x = point_value.x, y = point_value.y } end

local function rectangle(rectangle_value)
  return {
    x = rectangle_value.x,
    y = rectangle_value.y,
    width = rectangle_value.width,
    height = rectangle_value.height,
  }
end

local function resolve_layer(sprite, path)
  assert(path ~= nil and #path > 0, "invalid target Layer path")
  local layers = sprite.layers
  local layer = nil
  for _, index in ipairs(path) do
    assert(
      type(index) == "number" and index % 1 == 0 and index >= 1,
      "invalid target Layer path index"
    )
    layer = layers[index]
    assert(layer ~= nil, "target Layer does not exist")
    layers = layer.layers
  end
  return layer
end

local function find_layer_path(layers, target, prefix)
  for index = 1, #layers do
    local layer = layers[index]
    local path = {}
    for _, value in ipairs(prefix) do
      path[#path + 1] = value
    end
    path[#path + 1] = index
    if layer == target then return path end
    if layer.isGroup then
      local nested = find_layer_path(layer.layers, target, path)
      if nested ~= nil then return nested end
    end
  end
  return nil
end

local function resolve_target(sprite, address, allow_missing_cel)
  assert(address ~= nil, "missing target Cel address")
  assert(
    type(address.frame_number) == "number"
      and address.frame_number % 1 == 0
      and address.frame_number >= 1
      and address.frame_number <= #sprite.frames,
    "target Frame does not exist"
  )
  local layer = resolve_layer(sprite, address.layer_path)
  assert(
    layer.isImage and not layer.isGroup and not layer.isTilemap and not layer.isReference,
    "target Layer is not a regular Image Layer"
  )
  local cel = layer:cel(address.frame_number)
  local image = cel ~= nil and cel.image or nil
  if not allow_missing_cel then assert(image ~= nil, "target Cel does not exist") end
  return layer, cel, image
end

function module.missing_target_cel(sprite, address)
  if address.frame_number > #sprite.frames then return false end
  local _, _, image = resolve_target(sprite, address, true)
  return image == nil
end

local function validate_selection(selection)
  if selection == nil or selection.kind == "empty" then return end
  assert(selection.kind == "all" or selection.kind == "mask", "unsupported Selection Application")
  local bounds = selection.kind == "all" and selection.rectangle or selection.bounds
  assert(
    bounds ~= nil
      and type(bounds.x) == "number"
      and type(bounds.y) == "number"
      and type(bounds.width) == "number"
      and type(bounds.height) == "number"
      and bounds.width % 1 == 0
      and bounds.height % 1 == 0
      and bounds.width > 0
      and bounds.height > 0,
    "invalid Selection bounds"
  )
  if selection.kind == "all" then return end
  assert(selection.rows ~= nil and #selection.rows > 0, "Mask Selection must contain rows")
  local previous_y = nil
  local min_x, max_x = nil, nil
  for _, row in ipairs(selection.rows) do
    assert(type(row.y) == "number" and row.y % 1 == 0, "invalid Mask Selection row")
    assert(
      previous_y == nil or row.y > previous_y,
      "Mask Selection rows must be ordered and unique"
    )
    assert(
      row.y >= bounds.y and row.y < bounds.y + bounds.height,
      "Mask Selection row is outside its bounds"
    )
    assert(row.runs ~= nil and #row.runs > 0, "Mask Selection row must contain runs")
    local previous_end = nil
    for _, run in ipairs(row.runs) do
      assert(
        type(run.x) == "number"
          and run.x % 1 == 0
          and type(run.length) == "number"
          and run.length % 1 == 0
          and run.length > 0,
        "invalid Mask Selection run"
      )
      assert(
        run.x >= bounds.x and run.x + run.length <= bounds.x + bounds.width,
        "Mask Selection run is outside its bounds"
      )
      assert(
        previous_end == nil or run.x > previous_end,
        "Mask Selection runs must be ordered, non-overlapping, and non-adjacent"
      )
      previous_end = run.x + run.length
      min_x = min_x == nil and run.x or math.min(min_x, run.x)
      max_x = max_x == nil and run.x + run.length or math.max(max_x, run.x + run.length)
    end
    previous_y = row.y
  end
  assert(
    selection.rows[1].y == bounds.y
      and selection.rows[#selection.rows].y + 1 == bounds.y + bounds.height
      and min_x == bounds.x
      and max_x == bounds.x + bounds.width,
    "Mask Selection bounds are not tight"
  )
end

local function selection_contains(selection, x, y)
  if selection == nil then return true end
  if selection.kind == "empty" then return false end
  local bounds = selection.kind == "all" and selection.rectangle or selection.bounds
  if
    x < bounds.x
    or y < bounds.y
    or x >= bounds.x + bounds.width
    or y >= bounds.y + bounds.height
  then
    return false
  end
  if selection.kind == "all" then return true end
  for _, row in ipairs(selection.rows) do
    if row.y == y then
      for _, run in ipairs(row.runs) do
        if x >= run.x and x < run.x + run.length then return true end
      end
      return false
    elseif row.y > y then
      return false
    end
  end
  return false
end

local function append_segment(segments, x, y, color)
  local previous = segments[#segments]
  if
    previous ~= nil
    and previous.y == y
    and previous.x + previous.length == x
    and colors.colors_equal(previous.color, color)
  then
    previous.length = previous.length + 1
    return
  end
  segments[#segments + 1] = { x = x, y = y, length = 1, color = colors.copy_color(color) }
end

local function collect_affected_cels(sprite, target_image)
  local result = {}
  for cel_index = 1, #sprite.cels do
    local cel = sprite.cels[cel_index]
    if cel.image == target_image then
      local path = assert(
        find_layer_path(sprite.layers, cel.layer, {}),
        "could not resolve affected Cel Layer path"
      )
      result[#result + 1] = {
        layer_path = path,
        frame_number = cel.frame.frameNumber,
        position = point(cel.position),
        bounds = rectangle(cel.bounds),
        linked_to_target = true,
      }
    end
  end
  table.sort(result, function(left, right)
    if left.frame_number ~= right.frame_number then
      return left.frame_number < right.frame_number
    end
    local count = math.min(#left.layer_path, #right.layer_path)
    for index = 1, count do
      if left.layer_path[index] ~= right.layer_path[index] then
        return left.layer_path[index] < right.layer_path[index]
      end
    end
    return #left.layer_path < #right.layer_path
  end)
  assert(#result > 0, "target Image has no affected Cels")
  return result
end

local function background_is_opaque(sprite, image, color_mode, layer, affected_cels)
  if not layer.isBackground then return false end
  if color_mode == "indexed" then
    local indexes = {}
    for pixel in image:pixels() do
      indexes[pixel()] = true
    end
    local checked_frames = {}
    for _, cel in ipairs(affected_cels) do
      local frame_number = cel.frame_number
      if
        not checked_frames[frame_number]
        and resolve_layer(sprite, cel.layer_path).isBackground
      then
        local palette = colors.effective_palette(sprite, frame_number)
        for index, _ in pairs(indexes) do
          if index >= #palette or palette:getColor(index).alpha ~= 255 then return false end
        end
        checked_frames[frame_number] = true
      end
    end
    return true
  end
  for pixel in image:pixels() do
    local native = pixel()
    local alpha = color_mode == "rgb" and app.pixelColor.rgbaA(native)
      or app.pixelColor.grayaA(native)
    if alpha ~= 255 then return false end
  end
  return true
end

local function same_path(left, right)
  if #left ~= #right then return false end
  for index = 1, #left do
    if left[index] ~= right[index] then return false end
  end
  return true
end

local function validate_reopened(
  sprite,
  payload,
  evidence,
  expected_pixels,
  expected_affected,
  expected_geometry,
  digest
)
  local layer, _, image = resolve_target(sprite, payload.target)
  assert(colors.color_mode_name(sprite) == evidence.color_mode, "persisted Color Mode changed")
  assert(
    sprite.width == expected_geometry.sprite_width
      and sprite.height == expected_geometry.sprite_height
      and image.width == expected_geometry.image_width
      and image.height == expected_geometry.image_height,
    "persisted Sprite or Image geometry changed"
  )
  assert(
    layer.isBackground == expected_geometry.is_background
      and layer.isTransparent == expected_geometry.is_transparent,
    "persisted Layer transparency semantics changed"
  )
  local reopened_affected = collect_affected_cels(sprite, image)
  assert(#reopened_affected == #expected_affected, "persisted Linked Cel scope changed")
  for index, expected in ipairs(expected_affected) do
    local actual = reopened_affected[index]
    assert(
      same_path(actual.layer_path, expected.layer_path)
        and actual.frame_number == expected.frame_number,
      "persisted affected Cel identity changed"
    )
    assert(
      actual.position.x == expected.position.x
        and actual.position.y == expected.position.y
        and actual.bounds.x == expected.bounds.x
        and actual.bounds.y == expected.bounds.y
        and actual.bounds.width == expected.bounds.width
        and actual.bounds.height == expected.bounds.height,
      "persisted affected Cel geometry changed"
    )
  end
  for _, expected in ipairs(expected_pixels) do
    assert(
      image:getPixel(expected.x, expected.y) == expected.native,
      "persisted bounded pixel inspection failed"
    )
  end
  local content_digest = digest.image_content(image, evidence.color_mode)
  local opaque = background_is_opaque(sprite, image, evidence.color_mode, layer, reopened_affected)
  if layer.isBackground then assert(opaque, "persisted Background Image is not opaque") end
  return opaque, content_digest
end

local function restore_editor_state(previous)
  if previous.sprite ~= nil and previous.sprite.isValid then
    pcall(function() app.activeSprite = previous.sprite end)
    pcall(function() app.activeLayer = previous.layer end)
    pcall(function() app.activeFrame = previous.frame end)
  end
end

function module.apply_live(sprite, payload, digest)
  assert(payload.clipping == "reject" or payload.clipping == "clip", "unsupported clipping policy")
  assert(
    payload.patch ~= nil and payload.patch.coordinate_space == "image-pixel",
    "Pixel Patch must use Image Pixel coordinates"
  )
  local requested_rectangle = assert(payload.patch.rectangle)
  assert(
    type(requested_rectangle.x) == "number"
      and requested_rectangle.x % 1 == 0
      and type(requested_rectangle.y) == "number"
      and requested_rectangle.y % 1 == 0
      and type(requested_rectangle.width) == "number"
      and requested_rectangle.width % 1 == 0
      and requested_rectangle.width > 0
      and type(requested_rectangle.height) == "number"
      and requested_rectangle.height % 1 == 0
      and requested_rectangle.height > 0,
    "Pixel Patch Rectangle must be positive"
  )
  assert(payload.patch.runs ~= nil, "Pixel Patch runs are missing")
  validate_selection(payload.selection)

  local layer, cel, image = resolve_target(sprite, payload.target)
  local color_mode = colors.color_mode_name(sprite)
  local rectangle_in_bounds = requested_rectangle.x >= 0
    and requested_rectangle.y >= 0
    and requested_rectangle.x + requested_rectangle.width <= image.width
    and requested_rectangle.y + requested_rectangle.height <= image.height
  if payload.clipping == "reject" then
    assert(rectangle_in_bounds, "Pixel Patch Rectangle is outside Image bounds")
  end
  local affected_cels = collect_affected_cels(sprite, image)
  local expected_geometry = {
    sprite_width = sprite.width,
    sprite_height = sprite.height,
    image_width = image.width,
    image_height = image.height,
    is_background = layer.isBackground,
    is_transparent = layer.isTransparent,
  }
  local before_digest = digest.image_content(image, color_mode)
  local requested_runs = {}
  local applied_runs = {}
  local skipped_bounds = {}
  local skipped_selection = {}
  local plan = {}
  local inspected_pixels = {}
  local used_indexes = {}
  local pixels_requested = 0
  local pixels_skipped_by_bounds = 0
  local pixels_skipped_by_selection = 0
  local previous_y, previous_end, previous_color = nil, nil, nil
  for _, run in ipairs(payload.patch.runs) do
    assert(
      type(run.x) == "number"
        and run.x % 1 == 0
        and type(run.y) == "number"
        and run.y % 1 == 0
        and type(run.length) == "number"
        and run.length % 1 == 0
        and run.length > 0,
      "invalid Pixel Patch run"
    )
    assert(
      run.y >= requested_rectangle.y
        and run.y < requested_rectangle.y + requested_rectangle.height
        and run.x >= requested_rectangle.x
        and run.x + run.length <= requested_rectangle.x + requested_rectangle.width,
      "Pixel Patch run is outside its declared Rectangle"
    )
    assert(
      previous_y == nil or run.y > previous_y or (run.y == previous_y and run.x >= previous_end),
      "Pixel Patch runs must be ordered and non-overlapping"
    )
    if previous_y == run.y and run.x == previous_end then
      assert(
        not colors.colors_equal(previous_color, run.color),
        "adjacent equal Pixel Patch runs must be merged"
      )
    end
    local native = colors.native_color(run.color, color_mode, layer.isBackground)
    if color_mode == "indexed" then used_indexes[run.color.index] = true end
    requested_runs[#requested_runs + 1] = copy_run(run)
    pixels_requested = pixels_requested + run.length
    assert(
      #requested_runs <= max_patch_pixels and pixels_requested <= max_patch_pixels,
      "Pixel Patch exceeds the Operation Limit"
    )
    for x = run.x, run.x + run.length - 1 do
      local in_bounds = x >= 0 and run.y >= 0 and x < image.width and run.y < image.height
      if not in_bounds then
        assert(payload.clipping == "clip", "Pixel Patch pixel is outside Image bounds")
        append_segment(skipped_bounds, x, run.y, run.color)
        pixels_skipped_by_bounds = pixels_skipped_by_bounds + 1
      else
        local before = image:getPixel(x, run.y)
        local selected =
          selection_contains(payload.selection, x + cel.position.x, run.y + cel.position.y)
        if not selected then
          append_segment(skipped_selection, x, run.y, run.color)
          pixels_skipped_by_selection = pixels_skipped_by_selection + 1
          inspected_pixels[#inspected_pixels + 1] = { x = x, y = run.y, native = before }
        else
          append_segment(applied_runs, x, run.y, run.color)
          plan[#plan + 1] = {
            x = x,
            y = run.y,
            native = native,
            before = before,
          }
          inspected_pixels[#inspected_pixels + 1] = { x = x, y = run.y, native = native }
        end
      end
    end
    previous_y, previous_end, previous_color = run.y, run.x + run.length, run.color
  end
  local effective_palettes = colors.palette_facts(sprite, affected_cels, used_indexes)
  local pixels_changed = 0
  app.transaction("Apply Pixel Patch", function()
    for _, write in ipairs(plan) do
      if write.before ~= write.native then pixels_changed = pixels_changed + 1 end
      image:putPixel(write.x, write.y, write.native)
    end
  end)
  local applied_rectangle = {
    x = requested_rectangle.x,
    y = requested_rectangle.y,
    width = 0,
    height = 0,
  }
  if #plan > 0 then
    local min_x, min_y = plan[1].x, plan[1].y
    local max_x, max_y = min_x + 1, min_y + 1
    for _, write in ipairs(plan) do
      min_x, min_y = math.min(min_x, write.x), math.min(min_y, write.y)
      max_x, max_y = math.max(max_x, write.x + 1), math.max(max_y, write.y + 1)
    end
    applied_rectangle = {
      x = min_x,
      y = min_y,
      width = max_x - min_x,
      height = max_y - min_y,
    }
  end
  local evidence = {
    input_form = "inline",
    persisted_reopen_verified = false,
    target = copy_address(payload.target),
    color_mode = color_mode,
    clipping = payload.clipping,
    selection = copy_selection(payload.selection),
    requested_rectangle = copy_rectangle(requested_rectangle),
    applied_rectangle = applied_rectangle,
    requested_runs = requested_runs,
    applied_runs = applied_runs,
    skipped_by_bounds_runs = skipped_bounds,
    skipped_by_selection_runs = skipped_selection,
    pixels_requested = pixels_requested,
    pixels_written = #plan,
    pixels_changed = pixels_changed,
    pixels_skipped_by_bounds = pixels_skipped_by_bounds,
    pixels_skipped_by_selection = pixels_skipped_by_selection,
    pixel_partition_verified = true,
    affected_cels = affected_cels,
    linked_cels_preserved = true,
    geometry_unchanged = true,
    background_opaque = false,
    effective_palettes = effective_palettes,
    before_content_digest = before_digest,
  }
  local background_opaque, after_digest = validate_reopened(
    sprite,
    payload,
    evidence,
    inspected_pixels,
    affected_cels,
    expected_geometry,
    digest
  )
  evidence.background_opaque = background_opaque
  evidence.after_content_digest = after_digest
  return evidence, inspected_pixels, affected_cels, expected_geometry
end

function module.execute(payload, digest)
  assert(type(payload.source_sprite_file) == "string", "missing Source Sprite File")
  assert(type(payload.staged_sprite_file) == "string", "missing staged Sprite file")
  local previous = {
    sprite = app.activeSprite,
    layer = app.activeLayer,
    frame = app.activeFrame,
  }
  local open_sprite = nil
  local ok, result = pcall(function()
    open_sprite = assert(app.open(payload.source_sprite_file), "could not open Source Sprite File")
    if module.missing_target_cel(open_sprite, payload.target) then
      return { rejection = { code = "cel_not_found", message = "Cel or Image does not exist" } }
    end
    local evidence, inspected_pixels, affected_cels, expected_geometry =
      module.apply_live(open_sprite, payload, digest)
    assert(open_sprite:saveAs(payload.staged_sprite_file), "could not save staged Sprite")
    open_sprite:close()
    open_sprite = nil
    open_sprite = assert(app.open(payload.staged_sprite_file), "could not reopen staged Sprite")
    local background_opaque, after_digest = validate_reopened(
      open_sprite,
      payload,
      evidence,
      inspected_pixels,
      affected_cels,
      expected_geometry,
      digest
    )
    evidence.background_opaque = background_opaque
    evidence.after_content_digest = after_digest
    evidence.persisted_reopen_verified = true
    open_sprite:close()
    open_sprite = nil
    return evidence
  end)
  if open_sprite ~= nil then pcall(function() open_sprite:close() end) end
  restore_editor_state(previous)
  if not ok then error(result) end
  return result
end

return module
