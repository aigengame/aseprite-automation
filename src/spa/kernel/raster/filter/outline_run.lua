local filter = dofile(app.params.outline)
dofile(app.params.filter_run).execute(filter, "Outline")
