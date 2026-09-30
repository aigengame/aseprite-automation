-- Tag-owned exact selection in the current Sprite.tags order.
local module = {}

function module.resolve(sprite, address)
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

return module
