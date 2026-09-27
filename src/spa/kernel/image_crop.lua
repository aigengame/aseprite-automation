-- Strict Image crop; Cel placement remains separate from stored-pixel transformation.
local mutation = dofile(app.params.image_cel_mutation)
local transform = dofile(app.params.image_canvas_transform)
mutation.run("Image Crop", "image_transform_position_out_of_bounds", function(payload, source)
  local area = payload.rectangle
  if not transform.contains_rectangle(source, area) then
    return nil,
      mutation.reject(
        "image_crop_out_of_bounds",
        "Crop Rectangle must be contained in the source Image"
      )
  end
  local image, facts = transform.crop(source, area)
  local delta = payload.position_policy == "preserve_canvas_pixels" and { x = area.x, y = area.y }
    or { x = 0, y = 0 }
  facts.coordinate_space = "image-pixel"
  facts.rectangle = { x = area.x, y = area.y, width = area.width, height = area.height }
  facts.position_policy = payload.position_policy
  facts.position_delta = delta
  return image, delta, facts
end)
