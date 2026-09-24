-- Tag-owned native selection, mutation, and save/reopen verification.
local module = {}
local all_sections = {
  "frames",
  "tags",
  "palettes",
  "layers",
  "cels",
  "slices",
  "tilesets",
}
local directions = {
  forward = AniDir.FORWARD,
  reverse = AniDir.REVERSE,
  ping_pong = AniDir.PING_PONG,
  ping_pong_reverse = AniDir.PING_PONG_REVERSE,
}

local function selected_index(sprite, tag)
  for index, candidate in ipairs(sprite.tags) do
    if candidate == tag then return index end
  end
  error("mutated Tag is absent from Sprite.tags")
end

local function resolve(sprite, address)
  if address.tag_index ~= nil then
    local index = address.tag_index
    if type(index) ~= "number" or index % 1 ~= 0 or index < 1 or index > #sprite.tags then
      return nil, nil, "tag_missing", "Tag index is outside the current Sprite.tags order"
    end
    return sprite.tags[index], index
  end
  local match, number = nil, nil
  for index, tag in ipairs(sprite.tags) do
    if tag.name == address.tag_name then
      if match ~= nil then
        return nil, nil, "tag_ambiguous", "Tag name matches more than one Tag in the Sprite"
      end
      match, number = tag, index
    end
  end
  if match == nil then return nil, nil, "tag_missing", "No Tag matches the address" end
  return match, number
end

local function same_fact(a, b)
  return a.name == b.name
    and a.from_frame == b.from_frame
    and a.to_frame == b.to_frame
    and a.direction == b.direction
    and a.repeats == b.repeats
    and a.color.red == b.color.red
    and a.color.green == b.color.green
    and a.color.blue == b.color.blue
    and a.color.alpha == b.color.alpha
end

local function matching_occurrence(tags, index)
  local occurrence = 0
  for i = 1, index do
    if same_fact(tags[i], tags[index]) then occurrence = occurrence + 1 end
  end
  return occurrence
end

local function reopened_index(tags, selected, occurrence)
  for index, tag in ipairs(tags) do
    if same_fact(tag, selected) then
      occurrence = occurrence - 1
      if occurrence == 0 then return index end
    end
  end
  error("selected Tag was not preserved after reopening")
end

local function same_tag_multiset(left, right)
  if #left ~= #right then return false end
  local used = {}
  for _, tag in ipairs(left) do
    local found = false
    for index, other in ipairs(right) do
      if not used[index] and same_fact(tag, other) then
        used[index] = true
        found = true
        break
      end
    end
    if not found then return false end
  end
  return true
end

local function range_rejection(from, to, frame_count)
  return {
    rejection = {
      code = "tag_range_out_of_bounds",
      message = "Tag range must be ordered and within the Sprite timeline",
      details = { from_frame = from, to_frame = to, frame_count = frame_count },
    },
  }
end

local function color_value(value)
  return Color { r = value.red, g = value.green, b = value.blue, a = value.alpha }
end

local function apply(sprite, operation, properties, selected)
  local tag = selected
  app.transaction(operation .. " Tag", function()
    if operation == "add" then
      tag = sprite:newTag(properties.from_frame, properties.to_frame)
      tag.name = properties.name
      tag.aniDir = assert(directions[properties.direction], "invalid Tag direction")
      tag.repeats = properties.repeats
      if properties.color ~= nil then tag.color = color_value(properties.color) end
    elseif operation == "set" then
      if properties.to_frame ~= nil then tag.toFrame = properties.to_frame end
      if properties.from_frame ~= nil then tag.fromFrame = properties.from_frame end
      if properties.name ~= nil then tag.name = properties.name end
      if properties.direction ~= nil then
        tag.aniDir = assert(directions[properties.direction], "invalid Tag direction")
      end
      if properties.repeats ~= nil then tag.repeats = properties.repeats end
      if properties.color ~= nil then tag.color = color_value(properties.color) end
    elseif operation == "remove" then
      sprite:deleteTag(tag)
    else
      error("unsupported Tag mutation")
    end
  end)
  return tag
end

function module.execute(payload, inspection, digest, persistence)
  local open_sprite = nil
  local previous = { sprite = app.activeSprite, layer = app.activeLayer, frame = app.activeFrame }
  local ok, result = pcall(function()
    open_sprite = assert(app.open(payload.source_sprite_file), "could not open Source Sprite File")
    local before_count = #open_sprite.tags
    local selected, old_index
    if payload.operation ~= "add" then
      local code, message
      selected, old_index, code, message = resolve(open_sprite, assert(payload.target))
      if selected == nil then return { rejection = { code = code, message = message } } end
    end
    local properties = payload.properties or {}
    if payload.operation ~= "remove" then
      local from = properties.from_frame or (selected and selected.fromFrame.frameNumber)
      local to = properties.to_frame or (selected and selected.toFrame.frameNumber)
      if from < 1 or from > to or to > #open_sprite.frames then
        return range_rejection(from, to, #open_sprite.frames)
      end
    end
    local source_uuids = inspection.saved_layer_uuids(open_sprite, payload.source_sprite_file)
    local before = persistence.snapshot(open_sprite, inspection, digest, all_sections, source_uuids)
    local removed = selected and before.sprite.tags[old_index] or nil
    local tag = apply(open_sprite, payload.operation, properties, selected)
    local live = persistence.snapshot(open_sprite, inspection, digest, all_sections, source_uuids)
    local live_index = payload.operation ~= "remove" and selected_index(open_sprite, tag) or nil
    local live_tag = live_index and live.sprite.tags[live_index] or nil
    local occurrence = live_index and matching_occurrence(live.sprite.tags, live_index) or nil
    before.sprite.tags = live.sprite.tags
    before.sprite.metadata.tag_count = live.sprite.metadata.tag_count
    persistence.assert_same(before, live, "Tag mutation")
    assert(open_sprite:saveAs(payload.staged_sprite_file), "could not save staged Sprite")
    open_sprite:close()
    open_sprite = assert(app.open(payload.staged_sprite_file), "could not reopen staged Sprite")
    local target_uuids = inspection.saved_layer_uuids(open_sprite, payload.staged_sprite_file)
    local reopened =
      persistence.snapshot(open_sprite, inspection, digest, all_sections, target_uuids)
    assert(same_tag_multiset(live.sprite.tags, reopened.sprite.tags), "persisted Tags differ")
    live.sprite.tags = reopened.sprite.tags
    persistence.assert_same(live, reopened, "Tag mutation")
    local result_tag
    if payload.operation == "remove" then
      result_tag = {}
      for key, value in pairs(removed) do
        result_tag[key] = value
      end
      result_tag.tag_index = old_index
    else
      local index = reopened_index(reopened.sprite.tags, live_tag, occurrence)
      result_tag = {}
      for key, value in pairs(reopened.sprite.tags[index]) do
        result_tag[key] = value
      end
      result_tag.tag_index = index
    end
    return {
      before_tag_count = before_count,
      tag = result_tag,
      sprite = reopened.sprite,
      persisted_reopen_verified = true,
    }
  end)
  if open_sprite ~= nil then pcall(function() open_sprite:close() end) end
  if previous.sprite ~= nil and previous.sprite.isValid then
    pcall(function() app.activeSprite = previous.sprite end)
    pcall(function() app.activeLayer = previous.layer end)
    pcall(function() app.activeFrame = previous.frame end)
  end
  if not ok then error(result) end
  return result
end

return module
