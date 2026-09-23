-- Exercise Paint with editor Selection state present but no explicit Selection Application.
local paint = dofile(assert(app.params.paint))
local digest = dofile(assert(app.params.digest))
local source = assert(app.open(assert(app.params.source)))
source.selection:select(Rectangle(0, 0, 1, 1))

local result = paint.execute({
  source_sprite_file=app.params.source,
  staged_sprite_file=assert(app.params.target),
  target={ layer_path={ 1 }, frame_number=1 },
  patch={
    coordinate_space="image-pixel",
    rectangle={ x=0, y=0, width=2, height=1 },
    runs={{
      x=0, y=0, length=2,
      color={ kind="rgba", red=17, green=34, blue=51, alpha=255 },
    }},
  },
  clipping="reject",
}, digest)

assert(result.selection == nil)
assert(result.pixels_written == 2)
assert(result.pixels_skipped_by_selection == 0)
