local filter = dofile(app.params.brightness_contrast)
local tiles = dofile(app.params.filter_tiles)
dofile(app.params.filter_run).execute(filter, "Brightness/Contrast", tiles)
