-- Discriminating native Tool observations for Aseprite 1.3.18.5 issue #29.
-- This fixture never calls SPA's Paint implementation or supplies fallback pixels.
local red = app.pixelColor.rgba(255, 0, 0, 255)
local blue = app.pixelColor.rgba(0, 0, 255, 255)
local green = app.pixelColor.rgba(0, 255, 0, 255)

local function pixel_at(cel, x, y)
  local local_x, local_y = x - cel.position.x, y - cel.position.y
  local image = cel.image
  if local_x < 0 or local_y < 0 or local_x >= image.width or local_y >= image.height then
    return 0
  end
  return image:getPixel(local_x, local_y)
end

local function observe(sprite, baseline)
  local cel = assert(sprite.layers[1]:cel(1))
  local changed, fingerprint = 0, 0
  local left, top, right, bottom = 128, 128, -1, -1
  for y = 0, 127 do
    for x = 0, 127 do
      if pixel_at(cel, x, y) ~= baseline(x, y) then
        changed = changed + 1
        fingerprint = (fingerprint * 131 + x * 257 + y * 65537) % 2147483647
        left, top = math.min(left, x), math.min(top, y)
        right, bottom = math.max(right, x), math.max(bottom, y)
      end
    end
  end
  return { changed = changed, fingerprint = fingerprint, bounds = { left, top, right, bottom } }
end

local function use_tool(tool, cel, points)
  return app.useTool {
    tool = tool,
    cel = cel,
    color = Color { r = 255, g = 0, b = 0, a = 255 },
    brush = Brush { type = BrushType.CIRCLE, size = 1, angle = 0 },
    opacity = 255,
    points = points,
  }
end

-- First scripted use resets Spray preferences. Prime that path on a disposable Sprite.
local initial_sprites = #app.sprites
local primer = Sprite(1, 1, ColorMode.RGB)
use_tool("spray", primer.layers[1]:cel(1), { Point(0, 0) })
primer:close()
assert(#app.sprites == initial_sprites)

local function exercise(tool, points, options)
  options = options or {}
  local sprite = Sprite(128, 128, ColorMode.RGB)
  local cel = sprite.layers[1]:cel(1)
  local baseline
  if options.checker then
    for y = 0, 127 do
      for x = 0, 127 do
        cel.image:putPixel(x, y, (x + y) % 2 == 0 and blue or green)
      end
    end
    baseline = function(x, y) return (x + y) % 2 == 0 and blue or green end
  elseif options.same_color then
    cel.image:clear(red)
    baseline = function() return red end
  else
    baseline = function() return 0 end
  end

  local pref, old_width, old_speed
  if tool == "spray" then
    pref = app.preferences.tool(tool)
    old_width, old_speed = pref.spray.width, pref.spray.speed
    pref.spray.width, pref.spray.speed = options.width, options.speed
  end
  app.activeSprite, app.activeLayer, app.activeFrame = sprite, sprite.layers[1], sprite.frames[1]
  local ok, returned = pcall(use_tool, tool, cel, points)
  assert(ok, returned)
  local result = observe(sprite, baseline)
  result.returned_nil = returned == nil
  if pref then
    result.width, result.speed = pref.spray.width, pref.spray.speed
    pref.spray.width, pref.spray.speed = old_width, old_speed
    result.preferences_restored = pref.spray.width == old_width and pref.spray.speed == old_speed
  end
  sprite:close()
  assert(#app.sprites == initial_sprites)
  return result
end

local horizontal = {}
for x = 30, 90 do
  horizontal[#horizontal + 1] = Point(x, 64)
end
local result = {
  spray_narrow = exercise("spray", horizontal, { width = 2, speed = 100 }),
  spray_wide = exercise("spray", horizontal, { width = 16, speed = 100 }),
  spray_slow = exercise("spray", horizontal, { width = 16, speed = 1 }),
  spray_no_effect = exercise("spray", horizontal, { width = 16, speed = 100, same_color = true }),
  curve_a = exercise("curve", { Point(20, 60), Point(20, 20), Point(90, 20), Point(90, 60) }),
  curve_b = exercise("curve", { Point(20, 60), Point(20, 90), Point(90, 90), Point(90, 60) }),
  polygon_a = exercise("polygon", { Point(20, 20), Point(90, 20), Point(90, 90), Point(20, 90) }),
  polygon_b = exercise("polygon", { Point(20, 20), Point(90, 90), Point(90, 20), Point(20, 90) }),
  jumble_a = exercise("jumble", horizontal, { checker = true }),
  jumble_b = exercise("jumble", horizontal, { checker = true }),
}
print("SPA29_PROBE=" .. json.encode(result))
