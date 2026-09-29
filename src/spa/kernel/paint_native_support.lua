-- Native Paint policy and mutation evidence. Native Tool pixels have one private owner.
local module = {}
local tools = dofile(app.params.native_tool)
local cels = dofile(app.params.cel)
local layers = dofile(app.params.layer_select)
local colors = dofile(app.params.raster_color)
local masks = dofile(app.params.selection_mask)
local inspection = dofile(app.params.inspection)
local persistence = dofile(app.params.persistence)
local digest = dofile(app.params.digest)
local sections = { "frames", "tags", "palettes", "layers", "cels", "slices", "tilesets" }

local function reject(code, message) return { rejection = { code = code, message = message } } end

local function coverage()
  return { bounds = { x = 0, y = 0, width = 0, height = 0 }, rows = {}, pixel_count = 0 }
end

local function append(region, x, y)
  local rows = region.rows
  local row = rows[#rows]
  if row == nil or row.y ~= y then
    row = { y = y, runs = {} }
    rows[#rows + 1] = row
  end
  local runs = row.runs
  local run = runs[#runs]
  if run ~= nil and run.x + run.length == x then
    run.length = run.length + 1
  else
    runs[#runs + 1] = { x = x, length = 1 }
  end
  local b = region.bounds
  if region.pixel_count == 0 then
    b.x, b.y, b.width, b.height = x, y, 1, 1
  else
    local right, bottom = math.max(b.x + b.width, x + 1), math.max(b.y + b.height, y + 1)
    b.x, b.y = math.min(b.x, x), math.min(b.y, y)
    b.width, b.height = right - b.x, bottom - b.y
  end
  region.pixel_count = region.pixel_count + 1
end

-- Decoded JSON objects are userdata; copy request values before returning them
-- inside Lua result tables, where json.encode would otherwise emit null.
local function request_value(value)
  if type(value) ~= "table" and type(value) ~= "userdata" then return value end
  local copy = {}
  if value[1] ~= nil then
    for index, item in ipairs(value) do
      copy[index] = request_value(item)
    end
  else
    for key, item in pairs(value) do
      copy[key] = request_value(item)
    end
  end
  return copy
end

function module.apply_live(sprite, payload, tool, uuids)
  payload = request_value(payload)
  if payload.ink == "shading" then
    return reject("paint_capability_gap", "Shading Ink requires explicit Shade configuration")
  end
  assert(payload.coordinate_space == "image-pixel", "Paint requires Image Pixel geometry")
  assert(payload.clipping == "reject" or payload.clipping == "clip", "invalid clipping policy")
  local layer, _, refused = cels.resolve(sprite, payload.target, layers, uuids)
  if refused then return refused end
  if not (cels.is_regular_transparent(layer) or layer.isBackground) then
    return reject(
      "cel_unsupported_target",
      "Paint requires a regular Transparent or Background Layer"
    )
  end
  local cel = layer:cel(payload.target.frame_number)
  if cel == nil then return reject("cel_not_found", "Paint requires an existing Cel") end
  local image = cel.image
  local mode = colors.color_mode_name(sprite)
  local indexes = {}
  local function validate_color(value)
    colors.native_color(value, mode, false)
    if mode == "indexed" then indexes[value.index] = true end
  end
  if tool == "eraser" then
    local behavior = payload.behavior
    if behavior.kind == "erase" then
      if layer.isBackground then
        assert(behavior.background_color ~= nil, "Background erase requires background_color")
      else
        assert(behavior.background_color == nil, "Transparent erase accepts no Color")
      end
    end
    if behavior.foreground_color then validate_color(behavior.foreground_color) end
    if behavior.background_color then validate_color(behavior.background_color) end
  elseif tool ~= "blur" then
    validate_color(payload.color)
  end
  local affected = cels.affected(sprite, image)
  colors.palette_facts(sprite, affected, indexes)
  local selection = payload.selection ~= nil and masks.materialize(payload.selection) or nil
  local before = persistence.snapshot(sprite, inspection, digest, sections, uuids)
  local before_digest = digest.image_content(image, mode)
  local rendered = tools.render(sprite, cel, payload, tool)
  assert(
    rendered.image.width == image.width and rendered.image.height == image.height,
    "Native Paint output geometry changed"
  )
  local requested, applied, clipped, excluded = coverage(), coverage(), coverage(), coverage()
  local bounds = rendered.footprint.bounds
  local changed = 0
  -- Preflight the complete native footprint before touching the live shared Image.
  for y = bounds.y, bounds.y + bounds.height - 1 do
    for x = bounds.x, bounds.x + bounds.width - 1 do
      if rendered.footprint:contains(Point(x, y)) then
        append(requested, x, y)
        if x < 0 or y < 0 or x >= image.width or y >= image.height then
          assert(payload.clipping == "clip", "Native Brush footprint is outside Image bounds")
          append(clipped, x, y)
        elseif
          selection ~= nil and not selection:contains(Point(x + cel.position.x, y + cel.position.y))
        then
          append(excluded, x, y)
        else
          append(applied, x, y)
        end
      end
    end
  end
  -- A Transparent Layer's mask is a Sprite fact, not a Palette Entry. Explicit
  -- Color Values still use Palette validation; Background pixels do as well.
  local transparent_index = mode == "indexed" and not layer.isBackground and sprite.transparentColor
    or nil
  app.transaction("Native Paint", function()
    for _, row in ipairs(applied.rows) do
      for _, run in ipairs(row.runs) do
        for x = run.x, run.x + run.length - 1 do
          local native = rendered.image:getPixel(x, row.y)
          if image:getPixel(x, row.y) ~= native then changed = changed + 1 end
          image:putPixel(x, row.y, native)
          if mode == "indexed" and native ~= transparent_index then indexes[native] = true end
        end
      end
    end
  end)
  local opaque = colors.background_is_opaque(sprite, image)
  if layer.isBackground then assert(opaque, "Paint must preserve opaque Background pixels") end
  local after = persistence.snapshot(sprite, inspection, digest, sections, uuids)
  for index, item in ipairs(sprite.cels) do
    if item.image == image then before.images[index].content = after.images[index].content end
  end
  persistence.assert_equal(before, after, "Native Paint unrelated facts")
  local result = {
    target = payload.target,
    coordinate_space = "image-pixel",
    brush = payload.brush and {
      kind = payload.brush.kind,
      size = payload.brush.size,
      angle = payload.brush.angle or 0,
    },
    color = payload.color,
    ink = tool == "blur" and "blur" or payload.ink,
    requested_opacity = payload.opacity,
    effective_opacity = (payload.ink == "simple" or payload.ink == "copy-color") and 255
      or payload.opacity,
    clipping = payload.clipping,
    selection = payload.selection,
    color_mode = mode,
    requested_region = requested,
    applied_region = applied,
    clipped_region = clipped,
    selection_excluded_region = excluded,
    pixels_requested = requested.pixel_count,
    pixels_written = applied.pixel_count,
    pixels_changed = changed,
    pixels_skipped_by_bounds = clipped.pixel_count,
    pixels_skipped_by_selection = excluded.pixel_count,
    affected_cels = cels.affected(sprite, image),
    linked_cels_preserved = true,
    geometry_unchanged = true,
    background_opaque = opaque,
    effective_palettes = colors.palette_facts(sprite, affected, indexes),
    before_content_digest = before_digest,
    after_content_digest = digest.image_content(image, mode),
  }
  if tool == "paint_bucket" then
    result.seed, result.tolerance = payload.seed, payload.tolerance
    result.contiguous, result.connectivity = payload.contiguous, payload.connectivity
    result.refer_to, result.stop_at_grid = payload.refer_to, payload.stop_at_grid
    result.source_scope, result.effective_grid_cell =
      rendered.source_scope, rendered.effective_grid_cell
  elseif tool == "pencil" or tool == "eraser" or tool == "contour" or tool == "blur" then
    result.points, result.freehand_algorithm = payload.points, payload.freehand_algorithm
    if tool == "blur" then result.tiled_mode = payload.tiled_mode end
  elseif tool == "line" then
    result["from"], result.to = payload["from"], payload.to
  else
    result.bounds, result.style = payload.bounds, payload.style
  end
  if tool == "eraser" then
    result.behavior = payload.behavior
    result.native_behavior = payload.behavior.kind == "replace-foreground-with-background"
        and "foreground-replacement"
      or layer.isBackground and "background-color"
      or mode == "indexed" and "transparent-index"
      or "alpha-erasure"
    if result.native_behavior == "transparent-index" then
      result.transparent_index = sprite.transparentColor
    end
  end
  return result
end

function module.execute(payload, tool)
  local previous = { sprite = app.activeSprite, layer = app.activeLayer, frame = app.activeFrame }
  local sprite
  local ok, result = pcall(function()
    sprite = assert(app.open(payload.source_sprite_file), "could not open Source Sprite File")
    local uuids = inspection.saved_layer_uuids(sprite, payload.source_sprite_file)
    local evidence = module.apply_live(sprite, payload, tool, uuids)
    if evidence.rejection then return evidence end
    local expected = persistence.snapshot(sprite, inspection, digest, sections, uuids)
    assert(sprite:saveAs(payload.staged_sprite_file), "could not save Native Paint")
    sprite:close()
    sprite = assert(app.open(payload.staged_sprite_file), "could not reopen Native Paint")
    uuids = inspection.saved_layer_uuids(sprite, payload.staged_sprite_file)
    persistence.assert_same(
      expected,
      persistence.snapshot(sprite, inspection, digest, sections, uuids),
      "Native Paint"
    )
    evidence.persisted_reopen_verified = true
    return evidence
  end)
  if sprite ~= nil then pcall(function() sprite:close() end) end
  if previous.sprite ~= nil and previous.sprite.isValid then
    app.activeSprite, app.activeLayer, app.activeFrame =
      previous.sprite, previous.layer, previous.frame
  end
  if not ok then error(result) end
  return result
end

return module
