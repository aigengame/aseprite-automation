-- Native Selection materialization and canonical Canvas Pixel encoding.
local module = {}

function module.rectangle(area)
  return { x = area.x, y = area.y, width = area.width, height = area.height }
end

-- Lua bindings narrow coordinates to native integers. Refuse a lossy conversion
-- before it can wrap into a different, apparently successful Selection.
function module.native_rectangle(area)
  local result = Rectangle(area.x, area.y, area.width, area.height)
  local finish = Point(area.x + area.width, area.y + area.height)
  assert(
    result.x == area.x
      and result.y == area.y
      and result.width == area.width
      and result.height == area.height
      and finish.x == area.x + area.width
      and finish.y == area.y + area.height,
    "Selection Rectangle cannot be represented exactly by native coordinates"
  )
  return result
end

function module.copy(mask)
  local result = Selection()
  result:select(mask)
  return result
end

function module.translate(mask, x, y)
  if not mask.isEmpty then
    local b = module.rectangle(mask.bounds)
    b.x, b.y = b.x + x, b.y + y
    module.native_rectangle(b)
    mask.origin = Point(mask.origin.x + x, mask.origin.y + y)
    assert(mask.bounds.x == b.x and mask.bounds.y == b.y, "native Selection origin changed")
  end
  return mask
end

function module.contained(mask, area)
  if mask.isEmpty then return true end
  local b = mask.bounds
  return b.x >= area.x
    and b.y >= area.y
    and b.x + b.width <= area.x + area.width
    and b.y + b.height <= area.y + area.height
end

function module.validate(selection)
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
  module.native_rectangle(bounds)
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

function module.materialize(value)
  module.validate(value)
  local mask = Selection()
  if value.kind == "all" then
    local area = value.rectangle
    mask:add(module.native_rectangle(area))
  elseif value.kind == "mask" then
    for _, row in ipairs(value.rows) do
      for _, run in ipairs(row.runs) do
        mask:add(Rectangle(run.x, row.y, run.length, 1))
      end
    end
  else
    assert(value.kind == "empty", "unsupported Selection value")
  end
  return mask
end

function module.encode(mask)
  if mask.isEmpty then
    return { selection = { kind = "empty" }, pixel_count = 0, coordinate_space = "canvas-pixel" }
  end
  local area = mask.bounds
  local bounds = module.rectangle(area)
  local rows, count = {}, 0
  for y = area.y, area.y + area.height - 1 do
    local runs, start = {}, nil
    for x = area.x, area.x + area.width do
      local selected = x < area.x + area.width and mask:contains(Point(x, y))
      if selected then
        count = count + 1
        if start == nil then start = x end
      elseif start ~= nil then
        runs[#runs + 1] = { x = start, length = x - start }
        start = nil
      end
    end
    if #runs > 0 then rows[#rows + 1] = { y = y, runs = runs } end
  end
  local value = count == area.width * area.height and { kind = "all", rectangle = bounds }
    or { kind = "mask", bounds = bounds, rows = rows }
  return {
    selection = value,
    bounds = bounds,
    pixel_count = count,
    coordinate_space = "canvas-pixel",
  }
end

return module
