-- Selection operations use explicit values, never a caller's active Selection.
local module = {}
local masks = dofile(app.params.selection_mask)

local function with_sprite(width, height, operation)
  local previous = { sprite = app.activeSprite, layer = app.activeLayer, frame = app.activeFrame }
  local temporary
  local ok, result = pcall(function()
    temporary = Sprite(width, height, ColorMode.RGB)
    return operation(temporary)
  end)
  if temporary ~= nil then temporary:close() end
  app.activeSprite = previous.sprite
  if previous.sprite ~= nil and previous.sprite.isValid then
    app.activeLayer = previous.layer
    app.activeFrame = previous.frame
  end
  if not ok then error(result) end
  return result
end

function module.create(payload)
  local shape = payload.shape
  if shape.kind == "mask" then return masks.encode(masks.materialize(shape.input)) end
  if shape.kind == "rectangle" then
    return masks.encode(masks.materialize({ kind = "all", rectangle = shape.rectangle }))
  end
  assert(shape.kind == "ellipse", "unsupported Selection construction")
  local area = shape.bounds
  local result = with_sprite(area.width, area.height, function(sprite)
    app.useTool {
      tool = "elliptical_marquee",
      points = { Point(0, 0), Point(area.width - 1, area.height - 1) },
      selection = SelectionMode.REPLACE,
    }
    return masks.copy(sprite.selection)
  end)
  return masks.encode(masks.translate(result, area.x, area.y))
end

local function outside()
  return {
    rejection = {
      code = "selection_out_of_bounds",
      message = "Selected coverage is outside the declared Canvas Rectangle",
    },
  }
end

function module.invert(payload)
  local source = masks.materialize(payload.selection)
  if not masks.contained(source, payload.canvas) then return outside() end
  local canvas = masks.materialize({ kind = "all", rectangle = payload.canvas })
  canvas:subtract(source)
  local result = masks.encode(canvas)
  result.canvas = masks.rectangle(payload.canvas)
  return result
end

function module.combine(payload)
  local left, right = masks.materialize(payload.left), masks.materialize(payload.right)
  if payload.mode == "union" then
    left:add(right)
  elseif payload.mode == "intersect" then
    left:intersect(right)
  elseif payload.mode == "subtract" then
    left:subtract(right)
  else
    assert(payload.mode == "xor", "unsupported Selection combination")
    local common = masks.copy(left)
    common:intersect(right)
    left:add(right)
    left:subtract(common)
  end
  return masks.encode(left)
end

function module.run(operation)
  local ok, result = pcall(function()
    local file = assert(io.open(app.params.request, "rb"))
    local request = json.decode(file:read("*a"))
    file:close()
    assert(request.kernel_protocol_version == 1, "unsupported Kernel Protocol version")
    return operation(request.payload)
  end)
  local response = ok and { kernel_protocol_version = 1, status = "ok", result = result }
    or {
      kernel_protocol_version = 1,
      status = "error",
      cause = "operation_rejected",
      message = tostring(result),
    }
  local file = assert(io.open(app.params.response, "wb"))
  file:write(json.encode(response))
  file:close()
end

return module
