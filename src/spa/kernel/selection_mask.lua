-- Native Selection materialization and canonical Canvas Pixel encoding.
local module = {}

function module.rectangle(area)
  return { x = area.x, y = area.y, width = area.width, height = area.height }
end

function module.copy(mask)
  local result = Selection()
  result:select(mask)
  return result
end

function module.translate(mask, x, y)
  if not mask.isEmpty then mask.origin = Point(mask.origin.x + x, mask.origin.y + y) end
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

function module.materialize(value)
  local mask = Selection()
  if value.kind == "all" then
    local area = value.rectangle
    mask:add(Rectangle(area.x, area.y, area.width, area.height))
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
