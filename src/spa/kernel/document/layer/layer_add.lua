-- Fixed packaged Layer addition handler. Runtime files carry data only.
local kernel_protocol_version = 1
local inspection = dofile(app.params.inspection)
local selection = dofile(app.params.layer_select)
local open_sprite = nil
local previous = { sprite = app.activeSprite, layer = app.activeLayer, frame = app.activeFrame }

local function execute()
  local request_file = assert(io.open(app.params.request, "rb"))
  local request = json.decode(request_file:read("*a"))
  request_file:close()
  assert(
    request.kernel_protocol_version == kernel_protocol_version,
    "unsupported Kernel Protocol version"
  )
  local payload = assert(request.payload)
  open_sprite = assert(app.open(payload.source_sprite_file), "could not open Source Sprite")
  local verified_uuids = {}
  if payload.kind == "tilemap" or (payload.parent ~= nil and payload.parent.layer_uuid ~= nil) then
    verified_uuids = inspection.saved_layer_uuids(open_sprite, payload.source_sprite_file)
  end
  local parent = nil
  if payload.parent ~= nil then
    local selected, code, message = selection.resolve(open_sprite, payload.parent, verified_uuids)
    if selected == nil then
      open_sprite:close()
      open_sprite = nil
      return { rejection = { code = code, message = message } }
    end
    parent = selected.layer
    if not parent.isGroup then
      open_sprite:close()
      open_sprite = nil
      return {
        rejection = {
          code = "layer_parent_not_group",
          message = "New Layers require a Group parent",
        },
      }
    end
  end
  local before_layer_count = inspection.inspect(open_sprite, { "layers" }).metadata.layer_count
  local before_use_layer_uuids = open_sprite.useLayerUuids
  local tile_rules, tile_context
  if payload.kind == "tilemap" then
    tile_rules = dofile(app.params.tile_layer_creation)
    local failure
    tile_context, failure = tile_rules.prepare(open_sprite, payload.tileset, verified_uuids)
    if failure then return failure end
  end
  local new_layer
  app.transaction("Add Layer", function()
    if payload.kind == "transparent" then
      new_layer = open_sprite:newLayer()
    elseif payload.kind == "group" then
      new_layer = open_sprite:newGroup()
    elseif tile_rules then
      new_layer = tile_rules.create(open_sprite, payload.tileset, tile_context)
    else
      error("unsupported Layer kind")
    end
    new_layer.name = payload.name
    if parent ~= nil then new_layer.parent = parent end
    if tile_rules then
      new_layer.parent = parent or open_sprite
      new_layer.stackIndex = #(parent or open_sprite).layers
    end
  end)
  local added_path = {}
  local current = new_layer
  while current.parent ~= open_sprite do
    table.insert(added_path, 1, current.stackIndex)
    current = current.parent
  end
  table.insert(added_path, 1, current.stackIndex)
  if tile_rules then
    tile_rules.verify_existing(open_sprite, tile_context, added_path, verified_uuids)
    local persistence = dofile(app.params.persistence)
    -- save_verified consumes its Sprite, including on failure.
    local live = open_sprite
    open_sprite = nil
    open_sprite, verified_uuids = persistence.save_verified(
      live,
      payload.staged_sprite_file,
      verified_uuids,
      "Tilemap Layer creation"
    )
    tile_rules.verify_saved(open_sprite, tile_context)
  else
    assert(open_sprite:saveAs(payload.staged_sprite_file), "could not save staged Sprite")
    open_sprite:close()
    open_sprite = nil
    open_sprite = assert(app.open(payload.staged_sprite_file), "could not reopen staged Sprite")
    verified_uuids = inspection.saved_layer_uuids(open_sprite, payload.staged_sprite_file)
  end
  local result = {
    added_path = added_path,
    before_layer_count = before_layer_count,
    before_use_layer_uuids = before_use_layer_uuids,
    sprite = inspection.inspect(open_sprite, payload.inspection_scope, verified_uuids),
  }
  if tile_rules then
    local added =
      assert(selection.resolve(open_sprite, { layer_path = added_path }, verified_uuids))
    result.tilemap = tile_rules.observe(open_sprite, added.layer, tile_context, verified_uuids)
  end
  open_sprite:close()
  open_sprite = nil
  return result
end

local ok, result = pcall(execute)
if open_sprite ~= nil then pcall(function() open_sprite:close() end) end
if previous.sprite ~= nil and previous.sprite.isValid then
  pcall(function() app.activeSprite = previous.sprite end)
  pcall(function() app.activeLayer = previous.layer end)
  pcall(function() app.activeFrame = previous.frame end)
end
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
