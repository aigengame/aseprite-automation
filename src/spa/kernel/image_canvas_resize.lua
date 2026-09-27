-- Image canvas-resize: exact copy/fill geometry plus an explicit Cel placement policy.
local mutation = dofile(app.params.image_cel_mutation)
local transform = dofile(app.params.image_canvas_transform)
local frame = dofile(app.params.frame)
mutation.run(
  "Image Canvas Resize",
  "image_transform_position_out_of_bounds",
  function(payload, source, sprite, affected_cels)
    if not transform.compatible_fill(source, payload.fill) then
      return nil,
        mutation.reject(
          "image_canvas_fill_invalid",
          "Fill Color Value is incompatible with source Color Mode"
        )
    end
    if source.colorMode == ColorMode.INDEXED then
      for _, state in ipairs(affected_cels) do
        local effective = frame.effective_palette(sprite, state.frame_number)
        if payload.fill.index >= #effective then
          return nil,
            mutation.reject(
              "image_canvas_fill_invalid",
              "Fill Palette Index must exist in every affected Cel Frame Effective Palette"
            )
        end
      end
    end
    local image, facts =
      transform.canvas_resize(source, payload.width, payload.height, payload.offset, payload.fill)
    local delta = payload.position_policy == "preserve_source_canvas"
        and { x = -payload.offset.x, y = -payload.offset.y }
      or { x = 0, y = 0 }
    facts.coordinate_space = "image-pixel"
    facts.width, facts.height = payload.width, payload.height
    facts.offset = { x = payload.offset.x, y = payload.offset.y }
    facts.fill = {}
    for name, value in pairs(payload.fill) do
      facts.fill[name] = value
    end
    facts.position_policy = payload.position_policy
    facts.position_delta = delta
    return image, delta, facts
  end
)
