-- Frame-owned native insertion, Cel relationship, and persistence semantics.
local module = {}
local json_null = json.decode("null")
local all_sections = {
  "frames",
  "tags",
  "palettes",
  "layers",
  "cels",
  "slices",
  "tilesets",
}

local function duration_ms(frame) return math.floor(frame.duration * 1000 + 0.5) end

local function validate_duration(value)
  assert(
    type(value) == "number" and value % 1 == 0 and value >= 1 and value <= 65535,
    "duration_ms must be an integer from 1 through 65535"
  )
end

local function background_layer(sprite)
  for _, layer in ipairs(sprite.layers) do
    if layer.isBackground then return layer end
  end
  return nil
end

local function effective_palette(sprite, frame_number)
  local selected, selected_frame = nil, -1
  for palette_index = 1, #sprite.palettes do
    local palette = sprite.palettes[palette_index]
    local palette_frame = palette.frame.frameNumber
    if palette_frame <= frame_number and palette_frame > selected_frame then
      selected, selected_frame = palette, palette_frame
    end
  end
  return assert(selected, "Indexed Background has no Effective Palette")
end

module.effective_palette = effective_palette

local function validate_indexed_background(sprite, frame_number, index)
  local palette = effective_palette(sprite, frame_number)
  assert(index < #palette, "Background Palette Index does not exist")
  assert(palette:getColor(index).alpha == 255, "Background Palette Color is not opaque")
end

local function background_pixel(sprite, value, insert_number)
  assert(value ~= nil, "Background Layer requires background_color")
  if sprite.colorMode == ColorMode.RGB then
    assert(value.kind == "rgba" and value.alpha == 255, "RGB Background requires opaque rgba")
    return Color { r = value.red, g = value.green, b = value.blue, a = 255 },
      app.pixelColor.rgba(value.red, value.green, value.blue, 255)
  elseif sprite.colorMode == ColorMode.GRAY then
    assert(
      value.kind == "grayscale" and value.alpha == 255,
      "Grayscale Background requires opaque grayscale"
    )
    return Color { gray = value.gray, alpha = 255 }, app.pixelColor.graya(value.gray, 255)
  elseif sprite.colorMode == ColorMode.INDEXED then
    assert(value.kind == "palette-index", "Indexed Background requires palette-index")
    validate_indexed_background(sprite, math.max(1, insert_number - 1), value.index)
    return Color { index = value.index }, value.index
  end
  error("unsupported Background Color Mode")
end

module.background_pixel = background_pixel

function module.background_color_for_frame(sprite, value, frame_number)
  return background_pixel(sprite, value, frame_number + 1)
end

local function background_fill_fact(value)
  if value == nil or value == json_null then return json_null end
  if value.kind == "rgba" then
    return {
      kind = "rgba",
      red = value.red,
      green = value.green,
      blue = value.blue,
      alpha = value.alpha,
    }
  elseif value.kind == "grayscale" then
    return { kind = "grayscale", gray = value.gray, alpha = value.alpha }
  end
  return { kind = "palette-index", index = value.index }
end

local function tags(sprite)
  local result = {}
  for number, tag in ipairs(sprite.tags) do
    result[number] = {
      tag_number = number,
      name = tag.name,
      from_frame = tag.fromFrame.frameNumber,
      to_frame = tag.toFrame.frameNumber,
    }
  end
  return result
end

local function tag_adjustments(before, after)
  assert(#before == #after, "Frame insertion changed Tag count")
  local result = {}
  for i = 1, #before do
    local old, new = before[i], after[i]
    assert(old.name == new.name, "Frame insertion changed Tag identity")
    if old.from_frame ~= new.from_frame or old.to_frame ~= new.to_frame then
      result[#result + 1] = {
        tag_number = i,
        name = old.name,
        before_from_frame = old.from_frame,
        before_to_frame = old.to_frame,
        after_from_frame = new.from_frame,
        after_to_frame = new.to_frame,
      }
    end
  end
  return result
end

local function source_cels(sprite, number)
  local result = {}
  for _, cel in ipairs(sprite.cels) do
    if cel.frame.frameNumber == number then
      assert(cel.layer.isImage, "source Cel is not on an Image Layer")
      result[#result + 1] = cel
    end
  end
  return result
end

local function layer_path(sprite, layer)
  local path = {}
  local current = layer
  while current ~= sprite do
    table.insert(path, 1, current.stackIndex)
    current = current.parent
  end
  return path
end

function module.get_live(sprite, frame_number, inspection)
  assert(
    type(frame_number) == "number" and frame_number % 1 == 0 and frame_number >= 1,
    "Frame Number must be a positive integer"
  )
  local facts = inspection.inspect(sprite, { "frames" })
  local found = frame_number <= #sprite.frames
  return {
    found = found,
    frame = found and facts.frames[frame_number] or json_null,
    frames = facts.frames,
    frame_count = facts.metadata.frame_count,
  }
end

local function verify_cels(sprite, operation, input, inserted_number, source_count, expected_pixel)
  local inserted = source_cels(sprite, inserted_number)
  local relationships = {}
  if operation == "add" then
    local background = background_layer(sprite)
    assert(#inserted == (background and 1 or 0), "empty Frame has unexpected Cels")
    if background then
      local cel = assert(background:cel(inserted_number), "Background Cel is absent")
      assert(
        cel.bounds.x == 0
          and cel.bounds.y == 0
          and cel.bounds.width == sprite.width
          and cel.bounds.height == sprite.height,
        "Background Cel does not cover the Sprite"
      )
      for pixel in cel.image:pixels() do
        assert(pixel() == expected_pixel, "Background Cel differs from requested Color")
      end
      if sprite.colorMode == ColorMode.INDEXED then
        validate_indexed_background(sprite, inserted_number, expected_pixel)
      end
    end
  else
    assert(#inserted == source_count, "duplicate Frame did not preserve Cel presence")
    local source_number = input.source_frame_number
    for _, original in ipairs(source_cels(sprite, source_number)) do
      local copied = assert(original.layer:cel(inserted_number), "duplicated Cel is absent")
      local shared = original.image == copied.image
      assert(shared == (input.cel_mode == "link"), "Cel copy/link intent was not preserved")
      assert(original.bounds == copied.bounds, "duplicated Cel bounds differ")
      assert(original.opacity == copied.opacity, "duplicated Cel opacity differs")
      assert(original.zIndex == copied.zIndex, "duplicated Cel z-index differs")
      assert(original.image.bytes == copied.image.bytes, "duplicated Cel pixels differ")
      relationships[#relationships + 1] = {
        layer_path = layer_path(sprite, original.layer),
        source_frame_number = source_number,
        kind = shared and "link" or "copy",
      }
    end
  end
  return #inserted, relationships
end

local function insert(sprite, operation, input)
  local count = #sprite.frames
  local number
  local source_count = 0
  local expected_pixel = nil
  if operation == "add" then
    number = input.frame_number
    assert(number >= 1 and number <= count + 1, "Frame insertion position is out of range")
    validate_duration(input.duration_ms)
    local background = background_layer(sprite)
    if background then
      local color
      color, expected_pixel = background_pixel(sprite, input.background_color, number)
      app.bgColor = color
    else
      assert(
        input.background_color == nil or input.background_color == json_null,
        "background_color requires a Background Layer"
      )
    end
    sprite:newEmptyFrame(number)
    sprite.frames[number].duration = input.duration_ms / 1000
  else
    assert(operation == "duplicate", "unsupported Frame Operation")
    local source_number = input.source_frame_number
    assert(source_number >= 1 and source_number <= count, "source Frame does not exist")
    assert(input.cel_mode == "copy" or input.cel_mode == "link", "invalid Cel Mode")
    if input.duration_ms ~= nil and input.duration_ms ~= json_null then
      validate_duration(input.duration_ms)
    end
    number = source_number + 1
    local originals = source_cels(sprite, source_number)
    source_count = #originals
    local inherited_duration = duration_ms(sprite.frames[source_number])
    sprite:newEmptyFrame(number)
    app.activeSprite = sprite
    for _, original in ipairs(originals) do
      app.activeLayer = original.layer
      app.activeFrame = sprite.frames[source_number]
      app.command.NewFrame { content = input.cel_mode == "link" and "cellinked" or "celcopies" }
    end
    local desired = input.duration_ms
    if desired == nil or desired == json_null then desired = inherited_duration end
    sprite.frames[number].duration = desired / 1000
  end
  assert(#sprite.frames == count + 1, "Frame insertion did not add exactly one Frame")
  local inserted_count, relationships =
    verify_cels(sprite, operation, input, number, source_count, expected_pixel)
  return number, source_count, inserted_count, expected_pixel, relationships
end

function module.apply_live(sprite, operation, input)
  local before_tags = tags(sprite)
  local previous = {
    sprite = app.activeSprite,
    layer = app.activeLayer,
    frame = app.activeFrame,
    background_color = app.bgColor,
  }
  local evidence = nil
  local ok, failure = pcall(function()
    app.transaction(operation == "add" and "Add Frame" or "Duplicate Frame", function()
      local number, source_count, inserted_count, expected_pixel, relationships =
        insert(sprite, operation, input)
      evidence = {
        inserted_frame = { frame_number = number, duration_ms = duration_ms(sprite.frames[number]) },
        tag_adjustments = tag_adjustments(before_tags, tags(sprite)),
        source_cel_count = source_count,
        inserted_cel_count = inserted_count,
        background_fill = operation == "add" and background_fill_fact(input.background_color)
          or json_null,
        cel_relationships = relationships,
        cel_relationships_verified = true,
        persisted_reopen_verified = false,
        sprite = json_null,
        -- Private to the fixed handler; never returned as public evidence.
        _expected_pixel = expected_pixel,
      }
    end)
  end)
  pcall(function() app.bgColor = previous.background_color end)
  if previous.sprite ~= nil and previous.sprite.isValid then
    pcall(function() app.activeSprite = previous.sprite end)
    pcall(function() app.activeLayer = previous.layer end)
    pcall(function() app.activeFrame = previous.frame end)
  end
  if not ok then error(failure) end
  return assert(evidence)
end

function module.execute(payload, inspection, digest, persistence)
  local open_sprite = nil
  local previous = {
    sprite = app.activeSprite,
    layer = app.activeLayer,
    frame = app.activeFrame,
    background_color = app.bgColor,
  }
  local ok, result = pcall(function()
    open_sprite = assert(app.open(payload.source_sprite_file), "could not open Source Sprite File")
    local verified_uuids = inspection.saved_layer_uuids(open_sprite, payload.source_sprite_file)
    local input = assert(payload.input, "missing Frame input")
    local evidence = module.apply_live(open_sprite, payload.operation, input)
    local before =
      persistence.snapshot(open_sprite, inspection, digest, all_sections, verified_uuids)
    assert(open_sprite:saveAs(payload.staged_sprite_file), "could not save staged Sprite")
    open_sprite:close()
    open_sprite = assert(app.open(payload.staged_sprite_file), "could not reopen staged Sprite")
    verified_uuids = inspection.saved_layer_uuids(open_sprite, payload.staged_sprite_file)
    local after =
      persistence.snapshot(open_sprite, inspection, digest, all_sections, verified_uuids)
    persistence.assert_same(before, after, "Frame")
    local expected_pixel = evidence._expected_pixel
    local verified_count, verified_relationships = verify_cels(
      open_sprite,
      payload.operation,
      input,
      evidence.inserted_frame.frame_number,
      evidence.source_cel_count,
      expected_pixel
    )
    assert(verified_count == evidence.inserted_cel_count, "persisted Cel count differs")
    assert(
      #verified_relationships == #evidence.cel_relationships,
      "persisted Cel relationships differ"
    )
    assert(
      duration_ms(open_sprite.frames[evidence.inserted_frame.frame_number])
        == evidence.inserted_frame.duration_ms,
      "persisted Frame duration differs"
    )
    evidence.sprite = inspection.inspect(open_sprite, all_sections, verified_uuids)
    evidence.persisted_reopen_verified = true
    evidence._expected_pixel = nil
    open_sprite:close()
    open_sprite = nil
    return evidence
  end)
  if open_sprite ~= nil then pcall(function() open_sprite:close() end) end
  pcall(function() app.bgColor = previous.background_color end)
  if previous.sprite ~= nil and previous.sprite.isValid then
    pcall(function() app.activeSprite = previous.sprite end)
    pcall(function() app.activeLayer = previous.layer end)
    pcall(function() app.activeFrame = previous.frame end)
  end
  if not ok then error(result) end
  return result
end

return module
