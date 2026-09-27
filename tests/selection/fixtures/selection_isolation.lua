local selection = dofile(app.params.selection_support)

local function read(path)
  local file = assert(io.open(path, "rb"))
  local bytes = file:read("*a")
  file:close()
  return bytes
end

local function write(path, bytes)
  local file = assert(io.open(path, "wb"))
  file:write(bytes)
  file:close()
end

local caller = Sprite(12, 10, ColorMode.RGB)
local layer = caller:newLayer()
caller:newEmptyFrame()
local image = Image(3, 2, ColorMode.RGB)
for y = 0, 1 do
  for x = 0, 2 do
    image:drawPixel(x, y, Color(20 + x * 30, 40 + y * 50, 70, 255))
  end
end
caller:newCel(caller.layers[1], 1, Image(image), Point(1, 1))
caller:newCel(layer, 2, image, Point(5, 4))
caller:saveAs(app.params.source)
app.activeSprite = caller
app.activeLayer = layer
app.activeFrame = caller.frames[2]
caller.selection:select(Rectangle(1, 2, 4, 1))
caller.selection:add(Rectangle(1, 3, 1, 3))
local stored = read(app.params.source)
write(app.params.original, stored)
local count = #app.sprites
local pixels = {}
for index, cel in ipairs(caller.cels) do
  pixels[index] = { bytes = cel.image.bytes, position = cel.position }
end

local function preserved()
  assert(app.activeSprite == caller, "active Sprite changed")
  assert(app.activeLayer == layer, "active Layer changed")
  assert(app.activeFrame == caller.frames[2], "active Frame changed")
  assert(caller.width == 12 and caller.height == 10, "caller Canvas changed")
  assert(#caller.cels == #pixels, "caller Cel count changed")
  for index, cel in ipairs(caller.cels) do
    assert(cel.image.bytes == pixels[index].bytes, "caller pixel bytes changed")
    assert(cel.position == pixels[index].position, "caller Cel position changed")
  end
  assert(caller.selection.bounds == Rectangle(1, 2, 4, 4), "caller Selection bounds changed")
  for y = 0, 9 do
    for x = 0, 11 do
      local expected = (y == 2 and x >= 1 and x <= 4) or (x == 1 and y >= 3 and y <= 5)
      assert(caller.selection:contains(x, y) == expected, "caller Selection membership changed")
    end
  end
  assert(read(app.params.source) == stored, "stored caller bytes changed")
  assert(#app.sprites == count, "temporary Sprite leaked")
end

local canvas = { x = 0, y = 0, width = 20, height = 20 }
local input = {
  kind = "mask",
  bounds = { x = 5, y = 6, width = 4, height = 2 },
  rows = {
    { y = 6, runs = { { x = 5, length = 1 } } },
    { y = 7, runs = { { x = 5, length = 4 } } },
  },
}
local checked = {}
if app.params.scenario == "success" then
  local cases = {
    {
      "ellipse",
      function() return selection.create { shape = { kind = "ellipse", bounds = input.bounds } } end,
    },
    {
      "grow",
      function()
        return selection.grow { selection = input, canvas = canvas, radius = 1, shape = "circle" }
      end,
    },
    {
      "shrink",
      function()
        return selection.shrink {
          selection = { kind = "all", rectangle = { x = 5, y = 6, width = 5, height = 5 } },
          canvas = canvas,
          radius = 1,
          shape = "square",
        }
      end,
    },
    {
      "flip",
      function()
        return selection.transform {
          selection = input,
          canvas = canvas,
          transform = { kind = "flip", axis = "horizontal" },
        }
      end,
    },
    {
      "rotate",
      function()
        return selection.transform {
          selection = input,
          canvas = canvas,
          transform = { kind = "rotate", angle = 90 },
        }
      end,
    },
    {
      "scale",
      function()
        return selection.transform {
          selection = input,
          canvas = canvas,
          transform = { kind = "scale", width = 2, height = 1 },
        }
      end,
    },
  }
  for _, case in ipairs(cases) do
    local result = case[2]()
    assert(result.selection and result.pixel_count > 0, case[1] .. " did not succeed")
    preserved()
    checked[#checked + 1] = case[1]
  end
else
  -- Raise while Aseprite converts Rotate parameters, after a real temporary
  -- Sprite has been created. Keep the native command and native objects intact.
  local entered = 0
  local angle = setmetatable({}, {
    __tostring = function()
      assert(#app.sprites == count + 1, "failure did not enter temporary Sprite")
      assert(app.activeSprite ~= caller, "failure entered caller Sprite")
      entered = entered + 1
      error("injected native Rotate parameter failure")
    end,
  })
  local function fail()
    local ok, message = pcall(selection.transform, {
      selection = input,
      canvas = canvas,
      transform = { kind = "rotate", angle = angle },
    })
    assert(
      not ok and tostring(message):find("injected native Rotate parameter failure", 1, true),
      "native failure was lost or cleanup masked it"
    )
  end
  fail()
  assert(entered == 1)
  preserved()
  checked[#checked + 1] = "native_parameter_failure"
  caller:close()
  count = #app.sprites
  fail()
  assert(entered == 2)
  assert(#app.sprites == count, "failure without caller leaked temporary Sprite")
  assert(
    app.activeSprite == nil and app.activeLayer == nil and app.activeFrame == nil,
    "failure without caller left active state"
  )
  checked[#checked + 1] = "failure_without_caller"
end
write(
  app.params.out,
  json.encode {
    checked = checked,
    caller_preserved = true,
    temporary_sprites_closed = true,
  }
)
if caller.isValid then caller:close() end
