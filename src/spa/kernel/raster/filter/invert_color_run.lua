local filter = dofile(app.params.invert_color)
dofile(app.params.filter_run).execute(filter, "Invert Color")
