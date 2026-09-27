-- Selection operations use explicit values, never a caller's active Selection.
local module = {}
local masks = dofile(app.params.selection_mask)

local function with_sprite(width, height, operation)
  local previous = { sprite = app.activeSprite, layer = app.activeLayer, frame = app.activeFrame }
  local temporary
  local ok, result = pcall(function()
    masks.native_rectangle { x = 0, y = 0, width = width, height = height }
    temporary = Sprite(width, height, ColorMode.RGB)
    assert(
      temporary.width == width and temporary.height == height,
      "native temporary Canvas differs from request"
    )
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
  masks.native_rectangle(area)
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
  if payload.canvas ~= nil then masks.native_rectangle(payload.canvas) end
  local source = masks.materialize(payload.selection)
  if not masks.contained(source, payload.canvas) then return outside() end
  local canvas = masks.materialize({ kind = "all", rectangle = payload.canvas })
  canvas:subtract(source)
  local result = masks.encode(canvas)
  result.canvas = masks.rectangle(payload.canvas)
  return result
end

local function morphology(payload, modifier)
  if payload.canvas ~= nil then masks.native_rectangle(payload.canvas) end
  local source = masks.materialize(payload.selection)
  local area = payload.canvas
  if not masks.contained(source, area) then return outside() end
  local transformed = source
  if not source.isEmpty then
    transformed = with_sprite(area.width, area.height, function(sprite)
      sprite.selection:select(masks.translate(source, -area.x, -area.y))
      app.command.ModifySelection {
        ui = false,
        modifier = modifier,
        quantity = payload.radius,
        brush = payload.shape,
      }
      return masks.translate(masks.copy(sprite.selection), area.x, area.y)
    end)
  end
  local result = masks.encode(transformed)
  result.canvas = masks.rectangle(area)
  result.radius, result.shape = payload.radius, payload.shape
  return result
end

function module.grow(payload) return morphology(payload, "expand") end
function module.shrink(payload) return morphology(payload, "contract") end

function module.transform(payload)
  if payload.canvas ~= nil then masks.native_rectangle(payload.canvas) end
  local source = masks.materialize(payload.selection)
  if not masks.contained(source, payload.canvas) then return outside() end
  local transform = payload.transform
  local source_bounds, placement
  local transformed = source
  if not source.isEmpty then
    source_bounds = masks.rectangle(source.bounds)
    placement = masks.rectangle(source.bounds)
    if transform.kind == "translate" then
      placement.x = placement.x + transform.offset.x
      placement.y = placement.y + transform.offset.y
      transformed = masks.translate(source, transform.offset.x, transform.offset.y)
    else
      if transform.kind == "scale" then
        placement.width, placement.height = transform.width, transform.height
      elseif transform.kind == "rotate" and transform.angle ~= 180 then
        placement.width, placement.height = placement.height, placement.width
      end
      masks.native_rectangle(placement)
      transformed = with_sprite(source_bounds.width, source_bounds.height, function(sprite)
        local local_mask = masks.translate(source, -source_bounds.x, -source_bounds.y)
        sprite.selection:select(local_mask)
        if transform.kind == "flip" then
          app.command.Flip { target = "mask", orientation = transform.axis }
        elseif transform.kind == "rotate" then
          app.command.Rotate { target = "sprite", angle = transform.angle, ui = false }
        else
          assert(transform.kind == "scale", "unsupported Selection transform")
          -- Adapt the binary Mask to an Image; Aseprite owns all sampling.
          local image = Image(source_bounds.width, source_bounds.height, ColorMode.RGB)
          for y = 0, image.height - 1 do
            for x = 0, image.width - 1 do
              if local_mask:contains(Point(x, y)) then
                image:drawPixel(x, y, Color(255, 255, 255, 255))
              end
            end
          end
          image:resize {
            width = placement.width,
            height = placement.height,
            method = "nearest-neighbor",
          }
          sprite:newCel(sprite.layers[1], 1, image, Point(0, 0))
          sprite.selection:deselect()
          app.command.MaskByColor {
            ui = false,
            color = Color(255, 255, 255, 255),
            tolerance = 0,
            mode = "replace",
          }
        end
        return masks.translate(masks.copy(sprite.selection), placement.x, placement.y)
      end)
    end
  end
  if not masks.contained(transformed, payload.canvas) then return outside() end
  local result = masks.encode(transformed)
  result.canvas = masks.rectangle(payload.canvas)
  result.source_bounds, result.target_placement = source_bounds, placement
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

local function write_file(path, bytes)
  local file = assert(io.open(path, "wb"))
  assert(file:write(bytes))
  assert(file:close())
end

function module.export(payload)
  local result = masks.encode(masks.materialize(payload.selection))
  write_file(payload.staged_file, json.encode(result.selection))
  return result
end

function module.preview(payload)
  local mask = masks.materialize(payload.selection)
  local area = payload.canvas
  masks.native_rectangle(area)
  if not masks.contained(mask, area) then return outside() end
  local image = Image(area.width, area.height, ColorMode.RGB)
  for y = 0, area.height - 1 do
    for x = 0, area.width - 1 do
      if mask:contains(Point(x + area.x, y + area.y)) then
        image:drawPixel(x, y, Color(255, 255, 255, 255))
      end
    end
  end
  write_file(payload.rendered_file, image.bytes)
  assert(image:saveAs(payload.staged_file), "native Preview PNG encoding failed")
  return masks.encode(mask)
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
