-- Palette export uses a private Source Sprite; only the verified Palette file is published.
local palettes = dofile(app.params.palette)
local effective = dofile(app.params.effective_palette)
local quantization = dofile(app.params.palette_quantization)
local sprite
local previous = { sprite = app.activeSprite, layer = app.activeLayer, frame = app.activeFrame }

local function execute()
  local file = assert(io.open(app.params.request, "rb"))
  local request = json.decode(file:read("*a"))
  file:close()
  assert(request.kernel_protocol_version == 1, "unsupported Kernel Protocol version")
  local payload = assert(request.payload)
  sprite = assert(app.open(payload.source_sprite_file), "could not open Source Sprite File")
  local choice = payload.palette_source
  local result, frame
  if choice.kind == "effective" then
    local selected = palettes.get(sprite, choice.frame_number)
    if selected.rejection then return selected end
    frame = tonumber(choice.frame_number)
    result = palettes.list(sprite)
    result.palette = selected.palette
  else
    result = quantization.generate(sprite, choice)
    if result.rejection then return result end
    frame = tonumber(choice.palette_frame_number)
  end
  local selected = effective.resolve(sprite, frame)
  if payload.format == "png" and #selected > 256 then
    return {
      rejection = {
        code = "palette_export_rejected",
        details = {
          reason = "indexed_png_capacity",
          palette_size = #selected,
        },
      },
    }
  end
  app.activeSprite = sprite
  app.activeFrame = sprite.frames[frame]
  selected:saveAs(payload.staged_palette_file)
  return result
end

local ok, result = pcall(execute)
if sprite ~= nil then pcall(function() sprite:close() end) end
if previous.sprite ~= nil and previous.sprite.isValid then
  app.activeSprite, app.activeLayer, app.activeFrame =
    previous.sprite, previous.layer, previous.frame
end
local response
if ok then
  response = { kernel_protocol_version = 1, status = "ok", result = result }
else
  response = {
    kernel_protocol_version = 1,
    status = "error",
    cause = "operation_rejected",
    message = tostring(result),
  }
end
local file = assert(io.open(app.params.response, "wb"))
file:write(json.encode(response))
file:close()
