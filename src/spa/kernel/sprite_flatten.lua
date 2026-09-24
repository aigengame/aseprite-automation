-- Fixed packaged native Sprite flatten handler. Runtime files carry data only.
local kernel_protocol_version = 1
local inspection = dofile(app.params.inspection)
local persistence = dofile(app.params.persistence)
local digest = dofile(app.params.digest)
local all_sections = {
  "frames",
  "tags",
  "palettes",
  "layers",
  "cels",
  "slices",
  "tilesets",
}
local open_sprite = nil

local function tilemap_layer_count(layers)
  local count = 0
  for _, layer in ipairs(layers) do
    if layer.isTilemap then count = count + 1 end
    if layer.isGroup then count = count + tilemap_layer_count(layer.layers) end
  end
  return count
end

local function execute()
  local request_file = assert(io.open(app.params.request, "rb"))
  local request = json.decode(request_file:read("*a"))
  request_file:close()
  assert(
    request.kernel_protocol_version == kernel_protocol_version,
    "unsupported Kernel Protocol version"
  )
  local payload = assert(request.payload)
  open_sprite = assert(app.open(payload.source_sprite_file), "could not open Source Sprite File")
  local tilesets = #open_sprite.tilesets
  local tilemaps = tilemap_layer_count(open_sprite.layers)
  if tilesets > 0 or tilemaps > 0 then
    open_sprite:close()
    open_sprite = nil
    return {
      rejection = {
        kind = "sprite_content",
        tileset_count = tilesets,
        tilemap_layer_count = tilemaps,
      },
    }
  end

  local verified_uuids = inspection.saved_layer_uuids(open_sprite, payload.source_sprite_file)
  local before = inspection.inspect(open_sprite, all_sections, verified_uuids)
  open_sprite:flatten()
  local after_live = persistence.snapshot(open_sprite, inspection, digest, all_sections, {})
  assert(open_sprite:saveAs(payload.staged_sprite_file), "could not save staged Sprite")
  open_sprite:close()
  open_sprite = assert(app.open(payload.staged_sprite_file), "could not reopen staged Sprite")
  verified_uuids = inspection.saved_layer_uuids(open_sprite, payload.staged_sprite_file)
  local after = persistence.snapshot(open_sprite, inspection, digest, all_sections, verified_uuids)
  persistence.assert_same(after_live, after, "Sprite flatten")
  open_sprite:close()
  open_sprite = nil
  return {
    before_sprite = before,
    sprite = after.sprite,
    persisted_reopen_verified = true,
  }
end

local ok, result = pcall(execute)
if open_sprite ~= nil then pcall(function() open_sprite:close() end) end
local response
if ok then
  response = { kernel_protocol_version = kernel_protocol_version, status = "ok", result = result }
else
  response = {
    kernel_protocol_version = kernel_protocol_version,
    status = "error",
    cause = "operation_rejected",
    message = tostring(result),
  }
end
local response_file = assert(io.open(app.params.response, "wb"))
response_file:write(json.encode(response))
response_file:close()
