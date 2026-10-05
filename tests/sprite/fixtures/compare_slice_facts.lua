local persistence = dofile(app.params.persistence)
local function copy(value)
  if type(value) ~= "table" then return value end
  local result = {}
  for key, item in pairs(value) do
    result[key] = copy(item)
  end
  return result
end

local first = {
  name = "same",
  data = "same",
  color = { red = 12, green = 34, blue = 56, alpha = 78 },
  keys = {
    {
      frame_number = 1,
      bounds = { x = 1, y = 2, width = 3, height = 4 },
      center = json.decode("null"),
      pivot = json.decode("null"),
    },
    {
      frame_number = 3,
      bounds = { x = 2, y = 3, width = 4, height = 5 },
      center = { x = 1, y = 1, width = 2, height = 2 },
      pivot = { x = -1, y = 2 },
    },
  },
}
local second = copy(first)
second.color = { red = 0, green = 0, blue = 0, alpha = 0 }
local function snapshot(slices)
  return {
    sprite = {
      metadata = { color_mode = "indexed" },
      slices = copy(slices),
      frames = { { frame_number = 1 }, { frame_number = 2 } },
    },
  }
end

local function compare(before, after, expected, case)
  if app.params.nested == "true" then
    before, after = { document = before }, { document = after }
  end
  local equal
  if app.params.entry_point == "equal" then
    equal = persistence.equal(before, after)
  else
    equal = pcall(persistence[app.params.entry_point], before, after, "Slice facts")
  end
  assert(equal == expected, app.params.entry_point .. ": " .. case)
end

local before = snapshot { first, first, second }
compare(before, snapshot { second, first, first }, true, "reordered duplicate collection")
compare(snapshot {}, snapshot {}, true, "empty collection")
compare(before, snapshot { first, second, second }, false, "changed duplicate multiplicities")
compare(before, snapshot { first, second }, false, "missing Slice")
compare(before, snapshot { first, first, first, second }, false, "added Slice")
local keyless = copy(first)
keyless.keys = {}
compare(snapshot { keyless }, snapshot {}, false, "lost keyless Slice")

local changes = {
  name = function(fact) fact.name = "changed" end,
  data = function(fact) fact.data = "changed" end,
  color = function(fact) fact.color.blue = 99 end,
  frame = function(fact) fact.keys[2].frame_number = 4 end,
  bounds = function(fact) fact.keys[2].bounds.x = 99 end,
  center = function(fact) fact.keys[2].center.x = 99 end,
  pivot = function(fact) fact.keys[2].pivot.x = 99 end,
  missing_key = function(fact) table.remove(fact.keys, 2) end,
  key_order = function(fact)
    fact.keys[1], fact.keys[2] = fact.keys[2], fact.keys[1]
  end,
}
for case, change in pairs(changes) do
  local changed = copy(first)
  change(changed)
  compare(before, snapshot { second, changed, first }, false, case)
end
local reordered_frames = copy(before)
reordered_frames.sprite.frames[1], reordered_frames.sprite.frames[2] =
  reordered_frames.sprite.frames[2], reordered_frames.sprite.frames[1]
compare(before, reordered_frames, false, "other document arrays stay ordered")

local left, right = copy(before), copy(before)
left.extension, right.extension = { slices = { 1, 2 } }, { slices = { 2, 1 } }
compare(left, right, false, "unrelated fields named slices stay ordered")
