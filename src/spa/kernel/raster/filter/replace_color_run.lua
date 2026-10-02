local runner = dofile(app.params.filter_run)
runner.execute(dofile(app.params.replace_color), "Replace Color")
